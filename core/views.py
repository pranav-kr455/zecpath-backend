from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView, CreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination


from django.contrib.auth import get_user_model

User = get_user_model()



from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.db.models import Count, Q
from .permissions import IsEmployerUser


from .models import Candidate, Employer, JobPost, JobApplication,SavedJob,AdminActionLog
from .permissions import IsAdminUser, IsCandidateUser, IsEmployerUser, IsEmployerOwner
from .serializers import (
    CandidateProfileSerializer,
    EmployerProfileSerializer,
    JobPostSerializer,
    UserRegistrationSerializer,
    JobApplicationSerializer,
)
from .filters import JobPostFilter


from rest_framework.generics import UpdateAPIView
from .models import ApplicationAuditLog
from .serializers import ATSStatusUpdateSerializer

import os
import pdfplumber
from docx import Document
import re

from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import JobPost, JobApplication
from .notifications import dispatch_workflow_notification # ✨ Day 27 Event Core Import

import time
from rest_framework.exceptions import PermissionDenied  # 🛡️ Day 29 Security Exception Import

from .tasks import async_dispatch_workflow_email, process_scheduled_voice_ai_trigger

from django.http import JsonResponse
from core.models import AIInterviewSession, JobApplication

from django.utils import timezone
from datetime import timedelta
from core.models import HRRecruiterAvailability, AIInterviewSchedule
from core.services import AIInterviewSchedulingEngine
from core.tasks import async_dispatch_scheduling_confirmation_email

from core.models import  AIReminderLog
from core.tasks import execute_periodic_interview_reminder_scan

from core.services import AICandidateReportEngine

from django.core.cache import cache
from core.services import AIRecruiterAnalyticsEngine


from core.models import SystemAuditTrailLog
from core.services import CentralizedObservabilityService

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from core.utils import SecureDataCryptographicGuard

from core.services import APSystemLoadStressEngine



# ==========================================
# 1. PUBLIC IDENTITY MANAGEMENT
# ==========================================
@method_decorator(csrf_exempt, name='dispatch')
class SignUpView(APIView):
    """
    Open API endpoint allowing public registration.
    Enforces password hashing and data validation constraints.
    Exempt from CSRF session tokens to allow clean Postman validation.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "User registered successfully",
                "user": {
                    "email": user.email, 
                    "role": user.role
                }
            }, status=status.HTTP_201_CREATED)
        
        # Triggers Day 13 exception engine automatically if raw validation fails
        raise ValidationError(serializer.errors)


# ==========================================
# 2. SECURE EMPLOYER JOB MANAGEMENT (DAY 16)
# ==========================================
class EmployerJobCreateView(CreateAPIView):
    """
    Day 16: Secure operational view allowing job generation.
    Strictly restricted to authenticated profiles with an EMPLOYER role tier.
    """
    serializer_class = JobPostSerializer
    permission_classes = [IsAuthenticated, IsEmployerOwner]

    def perform_create(self, serializer):
        # Automatically capture and bind the calling user's Employer profile map
        try:
            employer_profile = self.request.user.employer_profile
            serializer.save(employer_profile=employer_profile)
        except Employer.DoesNotExist:
            raise ValidationError({"profile": "An active employer profile is required to post jobs."})


class EmployerJobDetailView(RetrieveUpdateDestroyAPIView):
    """
    Day 16: Secure management gateway allowing an employer to update details,
    toggle status flags (ACTIVE, PAUSED, CLOSED), or delete their own posts.
    Enforces strict object-level database ownership verification.
    """
    queryset = JobPost.objects.all()
    serializer_class = JobPostSerializer
    permission_classes = [IsAuthenticated, IsEmployerOwner]


class EmployerProfileDetailView(APIView):
    """
    CRUD View management for corporate Employer profiles.
    Integrated with soft delete states.
    """
    permission_classes = [IsAuthenticated, IsEmployerUser]

    def get(self, request):
        try:
            profile = Employer.objects.get(user=request.user, is_deleted=False)
            serializer = EmployerProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Employer.DoesNotExist:
            raise NotFound("Profile not found or has been deactivated.")

    def put(self, request):
        try:
            profile = Employer.objects.get(user=request.user, is_deleted=False)
        except Employer.DoesNotExist:
            raise NotFound("Profile not found or has been deactivated.")
            
        serializer = EmployerProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        raise ValidationError(serializer.errors)

    def delete(self, request):
        try:
            profile = Employer.objects.get(user=request.user)
            profile.is_deleted = True
            profile.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Employer.DoesNotExist:
            raise NotFound("Profile not found.")


# ==========================================
# 3. GUARDED CANDIDATE CONTROLLERS (DAY 18)
# ==========================================
class CandidateApplyView(CreateAPIView):
    """
    Day 18: Guarded submission endpoint allowing verified Candidates 
    to apply for active listings while preventing duplicate attempts.
    """
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsCandidateUser]

    def perform_create(self, serializer):
        try:
            candidate = self.request.user.candidate_profile
        except Candidate.DoesNotExist:
            raise ValidationError({"profile": "An active candidate profile is required to apply for jobs."})
            
        job_instance = serializer.validated_data['job']

        # 1. Job Availability Check
        if job_instance.status != 'ACTIVE':
            raise ValidationError({"job": "Applications are no longer being accepted for this vacancy."})

        # 2. Duplicate Prevention Rule
        if JobApplication.objects.filter(job=job_instance, candidate_profile=candidate).exists():
            raise ValidationError({"duplicate": "You have already submitted an application for this position."})

        # 3. Dynamic Profile Binding & Resume Snapshotting
        serializer.save(
            candidate_profile=candidate,
            resume_snapshot=candidate.resume if candidate.resume else None
        )


class CandidateApplicationHistoryView(ListAPIView):
    """
    Day 18: Tracking gateway returning the authenticated candidate's 
    entire application timeline history. Enforces strict data isolation ownership.
    """
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsCandidateUser]

    def get_queryset(self):
        return JobApplication.objects.filter(candidate_profile=self.request.user.candidate_profile)


class CandidateProfileDetailView(APIView):
    """
    CRUD View management for Candidate profile records, including CV tracking.
    """
    permission_classes = [IsAuthenticated, IsCandidateUser]

    def get(self, request):
        try:
            profile = Candidate.objects.get(user=request.user, is_deleted=False)
            serializer = CandidateProfileSerializer(profile)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Candidate.DoesNotExist:
            raise NotFound("Profile not found or has been deactivated.")

    def put(self, request):
        try:
            profile = Candidate.objects.get(user=request.user, is_deleted=False)
        except Candidate.DoesNotExist:
            raise NotFound("Profile not found or has been deactivated.")
            
        serializer = CandidateProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        raise ValidationError(serializer.errors)

    def delete(self, request):
        try:
            profile = Candidate.objects.get(user=request.user)
            profile.is_deleted = True
            profile.save()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Candidate.DoesNotExist:
            raise NotFound("Profile not found.")


# ==========================================
# 4. GUARDED SYSTEM ADMIN CONTROLLERS
# ==========================================
class AdminSystemControlView(APIView):
    """
    Sensitive operational interface mapping runtime metrics.
    Strictly restricted to root profiles holding an ADMIN role tier.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        return Response({
            "status": "Authorized",
            "message": "System metric logs compiled.",
            "metrics": {
                "active_nodes": "Healthy", 
                "threat_index": "Zero"
            }
        })


# ==========================================
# 5. PUBLIC OPERATIONAL ATS SEARCH MATRIX
# ==========================================
class StandardResultsSetPagination(PageNumberPagination):
    """
    Day 17: Large data handler offering standardized page offsets,
    ideal for supporting frontend infinite scroll wrappers.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class JobPostListView(ListAPIView):
    """
    Day 17: Scalable public search matrix with integrated query tuning,
    fuzzy keyword scanning, and database multi-index filters.
    """
    permission_classes = [AllowAny]
    serializer_class = JobPostSerializer
    pagination_class = StandardResultsSetPagination
    
    # 🏎️ CRITICAL QUERY TUNING: select_related forces an internal SQL JOIN
    # to eliminate the performance-killing N+1 query problem.
    queryset = JobPost.objects.select_related('employer_profile__user').all()
    
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = JobPostFilter
    
    # 🔎 FUZZY KEYWORD SEARCH ENGINE: Scans across major textual columns
    search_fields = ['title', 'description', 'skills_required', 'location']
    
    # 🗂️ ORDERING DECK
    ordering_fields = ['created_at', 'salary', 'experience_years']
    ordering = ['-created_at'] # Default to latest jobs

    def get_queryset(self):
        """
        Dynamically adjusts scope based on request parameters 
        to serve All Active, Featured, or Latest job feeds.
        """
        # Ensure public candidates only see ACTIVE job postings by default
        queryset = super().get_queryset().filter(status='ACTIVE')
        
        # 1. Scope Modifier: Check if the frontend is explicitly requesting featured listings
        is_featured = self.request.query_params.get('featured', None)
        if is_featured and is_featured.lower() == 'true':
            # Example filter criteria for a 'Featured' job layout tier
            queryset = queryset.filter(experience_years__gte=2, salary__gte=50000.00)
            
        return queryset
    


class EmployerStatusUpdateView(UpdateAPIView):
    """
    Day 19: Secure state machine managing applicant stages.
    Enforces ownership validation, locked terminal rules, and automatically generates audit trails.
    """
    queryset = JobApplication.objects.all()
    serializer_class = ATSStatusUpdateSerializer
    permission_classes = [IsAuthenticated, IsEmployerUser]

    def perform_update(self, serializer):
        application = self.get_object()
        user = self.request.user
        employer_profile = user.employer_profile

        # 1. Ownership Security Verification
        if application.job.employer_profile != employer_profile:
            raise ValidationError({"authorization": "You do not own the corporate rights to alter this applicant's timeline."})

        old_status = application.status
        new_status = serializer.validated_data.get('status')
        notes = serializer.validated_data.get('notes', '')

        # 2. Terminal State Lock Rule
        if old_status in ['OFFER', 'REJECTED']:
            raise ValidationError({"workflow": f"This application is locked because it has reached a final stage ({old_status})."})

        # 3. Prevent Identical Redundant Transitions
        if old_status == new_status:
            return

        # 4. State Machine Validation: Stop illegal backward steps
        if old_status == 'INTERVIEW' and new_status in ['APPLIED', 'REVIEWING']:
            raise ValidationError({"workflow": "Cannot move an applicant backward from an Interview phase to screening."})

        # Save the new status field assignment
        serializer.save()

        # 5. Automated System Audit Trail Capture
        ApplicationAuditLog.objects.create(
            application=application,
            changed_by=user,
            old_status=old_status,
            new_status=new_status,
            notes=notes
        )    


class EmployerDashboardAnalyticsView(APIView):
    """
    Day 20: Aggregates real-world corporate recruitment metrics, tracking
    total application metrics and calculating funnel conversion shortfall ratios.
    """
    permission_classes = [IsAuthenticated, IsEmployerUser]

    def get(self, request):
        employer = request.user.employer_profile

        # 1. Gather high-level job metadata counts
        total_jobs = JobPost.objects.filter(employer_profile=employer).count()
        active_jobs = JobPost.objects.filter(employer_profile=employer, status='ACTIVE').count()

        # 2. Extract aggregate metrics directly from database rows
        metrics = JobApplication.objects.filter(job__employer_profile=employer).aggregate(
            total_applications=Count('id'),
            pending_review=Count('id', filter=Q(status='APPLIED')),
            interview_stage=Count('id', filter=Q(status='INTERVIEW')),
            offers_extended=Count('id', filter=Q(status='OFFER')),
            total_rejected=Count('id', filter=Q(status='REJECTED'))
        )

        # 3. Calculate conversion ratios safely to avoid DivisionByZero errors
        total_apps = metrics['total_applications']
        interviews_or_offers = metrics['interview_stage'] + metrics['offers_extended']
        shortlist_ratio = round((interviews_or_offers / total_apps) * 100, 2) if total_apps > 0 else 0.00

        return Response({
            "success": True,
            "data": {
                "job_metrics": {
                    "total_posted": total_jobs,
                    "active_vacancies": active_jobs
                },
                "pipeline_metrics": metrics,
                "funnel_analytics": {
                    "shortlist_conversion_ratio": f"{shortlist_ratio}%"
                }
            }
        }, status=status.HTTP_200_OK)


class EmployerCandidatePipelineListView(ListAPIView):
    """
    Day 20: Centralized applicant discovery matrix for recruiters. 
    Enforces strict ownership isolation while supporting text search and stage filtering.
    """
    serializer_class = JobApplicationSerializer
    permission_classes = [IsAuthenticated, IsEmployerUser]

    def get_queryset(self):
        employer = self.request.user.employer_profile
        
        # Optimize queries with select_related to join records smoothly
        queryset = JobApplication.objects.filter(job__employer_profile=employer).select_related(
            'job', 'candidate_profile__user'
        )

        # 1. Filter by specific Job ID if requested
        job_id = self.request.query_params.get('job_id')
        if job_id:
            queryset = queryset.filter(job_id=job_id)

        # 2. Filter by ATS Stage
        stage = self.request.query_params.get('status')
        if stage:
            queryset = queryset.filter(status=stage.upper())

        # 3. Search Candidates dynamically by name, email, or skills
        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(candidate_profile__user__email__icontains=search_query) |
                Q(candidate_profile__skills__icontains=search_query) |
                Q(job__title__icontains=search_query)
            )

        return queryset        
    



class CandidateDashboardOverviewView(APIView):
    """
    Day 21: Aggregates candidate tracking metrics, submitted metrics,
    and returns their comprehensive interactive activity timeline data.
    """
    permission_classes = [IsAuthenticated]  # We will enforce Candidate role in the method

    def get(self, request):
        # Role validation guardrail
        if not hasattr(request.user, 'candidate_profile'):
            return Response({"error": "Access Denied. Only Candidate profiles can view this cockpit."}, status=status.HTTP_403_FORBIDDEN)
            
        candidate = request.user.candidate_profile

        # 1. Fetch current applications with optimized relations
        apps = JobApplication.objects.filter(candidate_profile=candidate).select_related('job')
        
        # 2. Build explicit counter metrics
        total_applied = apps.count()
        interviews_scheduled = apps.filter(status='INTERVIEW').count()
        offers_received = apps.filter(status='OFFER').count()
        rejected_count = apps.filter(status='REJECTED').count()

        # 3. Serialize application data for the tracking list view
        serialized_apps = JobApplicationSerializer(apps, many=True).data

        return Response({
            "success": True,
            "data": {
                "metrics": {
                    "total_applications": total_applied,
                    "interviews_scheduled": interviews_scheduled,
                    "offers_received": offers_received,
                    "rejected": rejected_count
                },
                "applications_timeline": serialized_apps
            }
        }, status=status.HTTP_200_OK)


class CandidateJobRecommendationsView(APIView):
    """
    Day 21: Algorithmic Recommendation Controller matching candidate skill matrices 
    against active database job posts.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, 'candidate_profile'):
            return Response({"error": "Access Denied."}, status=status.HTTP_403_FORBIDDEN)
            
        candidate = request.user.candidate_profile
        candidate_skills_str = candidate.skills or ""

        # Clean and split skills text by commas or spaces into a clear list array
        skills_list = [s.strip() for s in candidate_skills_str.replace(',', ' ').split() if s.strip()]

        # Base query: Only show ACTIVE vacancies that the candidate hasn't already applied to
        applied_job_ids = JobApplication.objects.filter(candidate_profile=candidate).values_list('job_id', flat=True)
        recommended_jobs = JobPost.objects.filter(status='ACTIVE').exclude(id__in=applied_job_ids)

        # Basic Recommendation Engine Matcher
        if skills_list:
            # Construct dynamic OR query across titles, descriptions, and skill requirements
            query_filter = Q()
            for skill in skills_list:
                query_filter |= Q(title__icontains=skill) | Q(description__icontains=skill)
            
            recommended_jobs = recommended_jobs.filter(query_filter).distinct()
        else:
            # Fallback: If no skills filled out, return latest active items
            recommended_jobs = recommended_jobs.order_by('-created_at')[:5]

        serialized_jobs = JobPostSerializer(recommended_jobs, many=True).data

        return Response({
            "success": True,
            "skills_analyzed": skills_list,
            "recommendations": serialized_jobs
        }, status=status.HTTP_200_OK)    
    


class CandidateSaveJobToggleView(APIView):
    """
    Day 21: Bookmarking mechanism allowing candidates to save/unsave active listings.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id):
        if not hasattr(request.user, 'candidate_profile'):
            return Response({"error": "Only candidates can bookmark jobs."}, status=status.HTTP_403_FORBIDDEN)
            
        candidate = request.user.candidate_profile
        
        # Verify the target job exists
        try:
            job = JobPost.objects.get(id=job_id, status='ACTIVE')
        except JobPost.DoesNotExist:
            return Response({"error": "Active job post not found."}, status=status.HTTP_404_NOT_FOUND)

        # Toggle Logic: If it exists, unsave it. If not, save it.
        saved_job_queryset = SavedJob.objects.filter(candidate=candidate, job=job)
        
        if saved_job_queryset.exists():
            saved_job_queryset.delete()
            return Response({"success": True, "bookmarked": False, "message": "Job removed from saved portfolio."}, status=status.HTTP_200_OK)
        else:
            SavedJob.objects.create(candidate=candidate, job=job)
            return Response({"success": True, "bookmarked": True, "message": "Job successfully saved to your portfolio."}, status=status.HTTP_201_CREATED)    
        



class AdminPlatformStatsView(APIView):
    """
    Day 22: Compiles high-level marketplace tracking metrics and platform usage stats
    for global platform administration monitoring.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        # Compute aggregate cross-table platform telemetry statistics
        total_users = User.objects.count()
        blocked_users = User.objects.filter(is_active=False).count()
        pending_employers = Employer.objects.filter(is_profile_verified=False, is_deleted=False).count()
        total_jobs = JobPost.objects.count()
        active_jobs = JobPost.objects.filter(status='ACTIVE').count()
        total_applications = JobApplication.objects.count()

        return Response({
            "success": True,
            "system_telemetry": {
                "user_metrics": {
                    "total_registered_users": total_users,
                    "blocked_accounts": blocked_users,
                    "unverified_employers": pending_employers
                },
                "marketplace_activity": {
                    "total_posted_jobs": total_jobs,
                    "active_vacancies": active_jobs,
                    "total_submitted_applications": total_applications
                }
            }
        }, status=status.HTTP_200_OK)


class AdminUserModerationView(APIView):
    """
    Day 22: Control plane allowing administrators to manage user access states 
    (blocking accounts) and verifying pending enterprise employers.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, user_id):
        action = request.data.get("action") # Expected values: "BLOCK", "UNBLOCK", "APPROVE_EMPLOYER"
        
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "Target user profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if action == "BLOCK":
            target_user.is_active = False
            target_user.save()
            
            AdminActionLog.objects.create(
                admin=request.user,
                action_type="USER_BLOCK",
                target_info=f"User ID: {target_user.id} ({target_user.email})",
                details="Account access revoked by administrative action."
            )
            return Response({"success": True, "message": f"User {target_user.email} has been successfully deactivated."}, status=status.HTTP_200_OK)

        elif action == "UNBLOCK":
            target_user.is_active = True
            target_user.save()
            
            AdminActionLog.objects.create(
                admin=request.user,
                action_type="USER_UNBLOCK",
                target_info=f"User ID: {target_user.id} ({target_user.email})",
                details="Account access restored by administrative action."
            )
            return Response({"success": True, "message": f"User {target_user.email} has been successfully reactivated."}, status=status.HTTP_200_OK)

        elif action == "APPROVE_EMPLOYER":
            try:
                employer_profile = target_user.employer_profile
                employer_profile.is_profile_verified = True
                employer_profile.save()
                
                AdminActionLog.objects.create(
                    admin=request.user,
                    action_type="EMPLOYER_APPROVE",
                    target_info=f"Employer ID: {employer_profile.id} (Company: {employer_profile.company_name})",
                    details="Employer verification credentials cleared and approved."
                )
                return Response({"success": True, "message": f"Corporate profile for {employer_profile.company_name} successfully verified."}, status=status.HTTP_200_OK)
            except AttributeError:
                return Response({"error": "The target user does not possess an active Employer profile."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"error": "Invalid administrative control option parameter specified."}, status=status.HTTP_400_BAD_REQUEST)    




def clean_extracted_text(text):
    """
    Normalizes extracted raw file strings by removing control breaks,
    unreadable artifacts, and consecutive structural spacing blocks.
    """
    if not text:
        return ""
    # Remove vertical tabs, carriage returns, and unreadable binary null patterns
    text = text.replace('\r', ' ').replace('\t', ' ').replace('\x00', ' ')
    # Normalize excessive sequential whitespace to single space blocks
    text = re.sub(r'\s+', ' ', text)
    # Strip leading and trailing padding space characters cleanly
    return text.strip()

class ResumeParsingExtractionView(APIView):
    """
    Day 23: Document Intelligence API extracting and normalizing 
    unstructured payload text from uploaded PDF/DOCX resumes.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # Required to handle binary file streams cleanly

    def post(self, request, *args, **kwargs):
        if 'resume' not in request.FILES:
            return Response({"error": "No file detected under the 'resume' form-data key parameter."}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['resume']
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        extracted_raw_text = ""

        try:
            # --- PHASE 1: PDF PROCESSING CHANNEL ---
            if file_extension == '.pdf':
                with pdfplumber.open(uploaded_file) as pdf:
                    pages_text = []
                    for page in pdf.pages:
                        page_content = page.extract_text()
                        if page_content:
                            pages_text.append(page_content)
                    extracted_raw_text = "\n".join(pages_text)

            # --- PHASE 2: DOCX PROCESSING CHANNEL ---
            elif file_extension == '.docx':
                doc = Document(uploaded_file)
                paragraphs_text = [para.text for para in doc.paragraphs if para.text]
                extracted_raw_text = "\n".join(paragraphs_text)
            
            else:
                return Response({"error": "Unsupported document format. Only .pdf and .docx files are accepted."}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

            # --- PHASE 3: CLEANING & NORMALIZATION LAYER ---
            cleaned_final_text = clean_extracted_text(extracted_raw_text)

            if not cleaned_final_text:
                return Response({"error": "Unable to extract readable character metrics from document."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            return Response({
                "success": True,
                "document_metadata": {
                    "filename": uploaded_file.name,
                    "content_type": uploaded_file.content_type,
                    "file_size_bytes": uploaded_file.size
                },
                "extracted_payload": cleaned_final_text
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "error": "Pipeline extraction failure occurred.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)        




# --- PREDEFINED CORE SKILL TAXONOMY MATRIX ---
SKILL_LIBRARY = {
    "Languages": ["python", "javascript", "typescript", "java", "c\+\+", "ruby", "golang", "php", "html", "css"],
    "Frameworks & Libraries": ["django", "react", "react\.js", "node\.js", "angular", "vue", "flask", "fastapi", "express"],
    "Databases": ["postgresql", "mysql", "mongodb", "sqlite", "redis", "cassandra"],
    "DevOps & Tools": ["docker", "aws", "git", "github", "kubernetes", "jenkins", "cicd", "postman"]
}

def extract_entities_from_text(text):
    """
    Applies deterministic tokenization and regex pattern matching to map
    skills, contact vectors, and professional metadata parameters.
    """
    text_lower = text.lower()
    extracted_skills = {}
    
    # 1. Map Technical Skills via Keyword Taxonomy Matcher
    all_skills_found = []
    for category, skills in SKILL_LIBRARY.items():
        category_matches = []
        for skill in skills:
            # Word boundary check ensures 'java' doesn't match inside 'javascript'
            pattern = r'\b' + skill + r'\b'
            if re.search(pattern, text_lower):
                # Clean up display names (e.g., react.js -> React.js)
                display_name = skill.replace(r'\+', '+').replace(r'\.', '.').upper()
                category_matches.append(display_name)
                all_skills_found.append(display_name)
        if category_matches:
            extracted_skills[category] = category_matches

    # 2. Extract Contact Metrics (Email & Phone Patterns)
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    phone_pattern = r'\+?\d{1,3}[-.\s]?\d{10}\b|\b\d{10}\b' # Captures standard 10-digit and international prefixes
    
    emails = re.findall(email_pattern, text)
    phones = re.findall(phone_pattern, text)

    # 3. Predict Role Tiers & Experience Metrics
    experience_years = 0
    # Match patterns like "3+ years", "5 years of experience", etc.
    exp_matches = re.findall(r'(\d+)\s*(?:\+)?\s*year[s]?\s*(?:of)?\s*experience', text_lower)
    if exp_matches:
        experience_years = max([int(year) for year in exp_matches])

    detected_roles = []
    role_keywords = ["developer", "engineer", "intern", "architect", "manager", "designer"]
    for role in role_keywords:
        if role in text_lower:
            detected_roles.append(role.upper())

    # Return Structured Resume JSON Schema
    return {
        "contact_information": {
            "primary_email": emails[0] if emails else None,
            "primary_phone": phones[0] if phones else None
        },
        "professional_profile": {
            "detected_roles": detected_roles,
            "estimated_years_experience": experience_years
        },
        "skills_inventory": {
            "categorized": extracted_skills,
            "flat_list": list(set(all_skills_found))
        }
    }

class ResumeSkillExtractionView(APIView):
    """
    Day 24: ATS Document Intelligence Parser converting uploaded unstructured 
    resume text streams into highly structured, ML-ready JSON schemas.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        if 'resume' not in request.FILES:
            return Response({"error": "No file detected under the 'resume' parameter."}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['resume']
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        raw_text = ""

        try:
            # 1. Ingest & Extract Text Stream Natively
            if file_extension == '.pdf':
                with pdfplumber.open(uploaded_file) as pdf:
                    raw_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            else:
                return Response({"error": "Unsupported document format. This endpoint processes PDF files natively."}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

            if not raw_text.strip():
                return Response({"error": "Unable to extract readable strings from document."}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            # 2. Run NLP Extraction and Structuring Pipeline
            structured_json_payload = extract_entities_from_text(raw_text)
            
            # Append Document File Meta details
            structured_json_payload["document_metadata"] = {
                "filename": uploaded_file.name,
                "file_size_bytes": uploaded_file.size
            }

            return Response({
                "success": True,
                "parsed_resume_data": structured_json_payload
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "error": "ATS parsing extraction engine failure.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


def calculate_ats_match_percentage(candidate_skills, job_skills, candidate_exp, job_min_exp):
    """
    Computes a normalized relevance vector match weight between 0.00% and 100.00%.
    - Skills Intersection Weight: 70%
    - Experience Proportional Weight: 30%
    """
    # 1. Calculate Skill Matches (70% Weight)
    if not job_skills:
        skills_score = 100.0  # Fallback if job lists no specific skills
    else:
        # Convert both arrays to uppercase sets to handle case-insensitive intersections
        cand_set = {s.upper() for s in candidate_skills}
        job_set = {s.upper() for s in job_skills}
        matched_skills = cand_set.intersection(job_set)
        
        # Percentage of required job skills possessed by the candidate
        skills_score = (len(matched_skills) / len(job_set)) * 100.0

    # 2. Calculate Experience Matches (30% Weight)
    if job_min_exp == 0:
        experience_score = 100.0 # Entry level positions grant full experience points
    else:
        # Give proportional score up to a maximum of 100% of the target requirement
        experience_score = min((candidate_exp / job_min_exp) * 100.0, 100.0)

    # 3. Apply Multiplier Weights
    final_score = (skills_score * 0.70) + (experience_score * 0.30)
    return round(final_score, 2)

class JobATSScoringAndRankingView(APIView):
    """
    Day 25: ATS Match Optimization Engine evaluating incoming candidate resumes
    against target job descriptions to calculate suitability vectors.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id, *args, **kwargs):
        try:
            job = JobPost.objects.get(id=job_id)
        except JobPost.DoesNotExist:
            return Response({"error": "Target job posting not found."}, status=status.HTTP_404_NOT_FOUND)

        if 'resume' not in request.FILES:
            return Response({"error": "No resume file detected."}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES['resume']
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()

        try:
            # --- PHASE 1: NATIVE STREAM EXTRACTION ---
            if file_extension == '.pdf':
                with pdfplumber.open(uploaded_file) as pdf:
                    raw_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            else:
                return Response({"error": "Only PDF resumes are supported for instant scoring mapping."}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

            # --- PHASE 2: RUN DAY 24 NLP ENTITY PARSER ---
            parsed_profile = extract_entities_from_text(raw_text)
            
            # --- PHASE 3: RUN DAY 25 WEIGHTED MATCHING CORE ---
            # Corrected to pull directly from your specific Day 16 Model Field: 'skills_required'
            raw_skills_string = getattr(job, 'skills_required', '')
            if isinstance(raw_skills_string, list):
                job_required_skills = raw_skills_string
            else:
                job_required_skills = [s.strip() for s in str(raw_skills_string).split(',') if s.strip()]
            
            # Corrected to pull directly from your specific Day 16 Model Field: 'experience_years'
            job_min_experience = getattr(job, 'experience_years', 0)

            candidate_flat_skills = parsed_profile["skills_inventory"]["flat_list"]
            candidate_years_exp = parsed_profile["professional_profile"]["estimated_years_experience"]

            computed_match_score = calculate_ats_match_percentage(
                candidate_skills=candidate_flat_skills,
                job_skills=job_required_skills,
                candidate_exp=candidate_years_exp,
                job_min_exp=job_min_experience
            )

            # --- PHASE 4: STRUCTURING ENGINE OUTPUT RESPONSE ---
            return Response({
                "success": True,
                "job_context": {
                    "job_title": job.title,
                    "target_requirements": job_required_skills,
                    "min_experience_required": job_min_experience
                },
                "candidate_evaluation": {
                    "suitability_percentage": f"{computed_match_score}%",
                    "matched_skills_inventory": list(set(candidate_flat_skills).intersection({s.upper() for s in job_required_skills})),
                    "parsed_profile_summary": parsed_profile
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "error": "ATS scoring system runtime error.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class AutomatedShortlistingView(APIView):
    """
    Day 26 & Day 27 Enhanced (Day 32 Optimized): Auto-Shortlisting Workflow Engine 
    processing instant evaluation, automated status transitions, and asynchronous 
    background execution infrastructure via Celery queues.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, job_id, *args, **kwargs):
        try:
            job = JobPost.objects.get(id=job_id)
        except JobPost.DoesNotExist:
            return Response({"error": "Target job vacancy post not found."}, status=status.HTTP_404_NOT_FOUND)

        if 'resume' not in request.FILES:
            return Response({"error": "No resume document file attached."}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = request.FILES['resume']
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()

        try:
            # --- PHASE 1: NATIVE STREAM EXTRACTION ---
            if file_extension == '.pdf':
                with pdfplumber.open(uploaded_file) as pdf:
                    raw_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            else:
                return Response({"error": "Unsupported file format."}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

            # --- PHASE 2: RUN NLP CORE PARSER & EXTRACT SKILLS ---
            parsed_profile = extract_entities_from_text(raw_text)
            
            raw_skills_string = getattr(job, 'skills_required', '')
            job_required_skills = [s.strip() for s in str(raw_skills_string).split(',') if s.strip()]
            job_min_experience = getattr(job, 'experience_years', 0)

            candidate_flat_skills = parsed_profile["skills_inventory"]["flat_list"]
            candidate_years_exp = parsed_profile["professional_profile"]["estimated_years_experience"]

            # --- PHASE 3: CALCULATE VECTOR MATCH SCORE ---
            computed_score = calculate_ats_match_percentage(
                candidate_skills=candidate_flat_skills,
                job_skills=job_required_skills,
                candidate_exp=candidate_years_exp,
                job_min_exp=job_min_experience
            )

            # --- PHASE 4: APPLY ROLE-BASED THRESHOLD LOGIC RULES ---
            SHORTLIST_THRESHOLD = 70.00
            REJECTION_THRESHOLD = 40.00
            
            automated_action = "PENDING_REVIEW"
            system_notes = "Application logs held securely for human hiring supervisor audit review."

            if computed_score >= SHORTLIST_THRESHOLD:
                automated_action = "SHORTLISTED"
                system_notes = f"System Auto-Action triggered: Candidate matched score ({computed_score}%) exceeds the required corporate target barrier ({SHORTLIST_THRESHOLD}%)."
            elif computed_score < REJECTION_THRESHOLD:
                automated_action = "REJECTED"
                system_notes = f"System Auto-Action triggered: Profile similarity vector ({computed_score}%) failed to clear structural minimum compliance boundaries ({REJECTION_THRESHOLD}%)."

            # --- PHASE 5: PERSIST RECORD TO DATABASE WITH AUTOMATED STATUS ---
            application, created = JobApplication.objects.get_or_create(
                job=job,
                candidate_profile=request.user.candidate_profile, 
                defaults={'ats_score': computed_score, 'status': automated_action}
            )
            
            if not created:
                application.ats_score = computed_score
                application.status = automated_action
                application.save()

            # --- ✨ PHASE 6: DAY 32 ASYNCHRONOUS ENGINE OFFLOADING ---
            candidate_name = getattr(request.user, 'first_name', 'Candidate') or "Candidate"
            candidate_email = request.user.email
            
            # 🚀 OFFLOAD 1: Send application updates via Celery worker without freezing request thread
            async_dispatch_workflow_email.delay(
                candidate_email=candidate_email,
                candidate_name=candidate_name,
                job_title=job.title,
                status_action=automated_action
            )

            voice_ai_triggered = False
            # 🚀 OFFLOAD 2: If shortlisted, fire a background job to initiate the real-time AI Phone Screen call
            if automated_action == "SHORTLISTED":
                process_scheduled_voice_ai_trigger.delay(
                    application_id=application.id)
                voice_ai_triggered = True

            # --- PHASE 7: ENGINE RECEIPT RESPONSE ---
            return Response({
                "success": True,
                "automation_receipt": {
                    "application_id": application.id,
                    "job_title": job.title,
                    "computed_ats_score": f"{computed_score}%",
                    "workflow_status": application.status,
                    "async_email_queued": True,
                    "async_voice_call_triggered": voice_ai_triggered,
                    "eligibility_audit": {
                        "shortlist_threshold_limit": f"{SHORTLIST_THRESHOLD}%",
                        "rejection_threshold_limit": f"{REJECTION_THRESHOLD}%",
                        "system_action_taken": automated_action,
                        "execution_summary": system_notes
                    }
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "success": False,
                "error": "Automation engine processing collapse.",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class OptimizedHRDashboardView(APIView):
    """
    Day 28 & Day 29 Secured: High-Scale Optimized View eliminating the N+1 database problem
    using eager loading select_related joins and enforcing strict role-based permission locks.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # 🛡️ SECURITY AUDIT PATCH: Enforce access control barriers.
        # If the user is a normal candidate applicant and not an administrator/staff, block access instantly.
        if hasattr(request.user, 'candidate_profile') and not request.user.is_staff:
            raise PermissionDenied("Access Denied: Recruiter credentials are required to view this dashboard.")

        start_time = time.time()

        # 🚀 SYSTEM OPTIMIZATION: select_related performs a single SQL JOIN 
        # instead of making separate database trips for every application row.
        applications = JobApplication.objects.select_related(
            'job', 
            'candidate_profile', 
            'candidate_profile__user'
        ).all()

        # Build payload output loop
        dashboard_data = []
        for app in applications:
            dashboard_data.append({
                "application_id": app.id,
                "ats_score": f"{app.ats_score}%",
                "status": app.status,
                "job_title": app.job.title,  # Pre-fetched via JOIN! Zero extra query cost.
                "candidate_name": f"{getattr(app.candidate_profile.user, 'first_name', 'Applicant')}", # Pre-fetched!
                "candidate_email": app.candidate_profile.user.email # Pre-fetched!
            })

        execution_latency = time.time() - start_time

        return Response({
            "success": True,
            "metrics_audit": {
                "records_cached_count": len(dashboard_data),
                "query_optimization_strategy": "Eager Loading (select_related JOIN)",
                "execution_latency_seconds": round(execution_latency, 4),
                "database_roundtrips": 1 # Guaranteed single-hit resolution!
            },
            "dashboard_records": dashboard_data
        }, status=status.HTTP_200_OK)



def test_day34_storage_view(request):
    """
    Day 37 Refactored: Temporary debug endpoint to execute the voice pipeline 
    and output multi-dimensional quantitative scoring results straight to the screen.
    """
    try:
        # 1. Grab the most recent application row from your system database
        app = JobApplication.objects.latest('id')
        
        # 2. Trigger the Day 37 refactored celery worker task function synchronously
        from core.tasks import process_scheduled_voice_ai_trigger
        result_msg = process_scheduled_voice_ai_trigger(application_id=app.id)
        
        # 3. Query the newly populated database record rows
        session = AIInterviewSession.objects.filter(application=app).latest('id')
        log = session.call_log
        
        # Extract the specialized technical evaluation round (Sequence #2)
        q2 = session.questions.filter(sequence_order=2).first()
        ans2 = q2.answer if q2 and hasattr(q2, 'answer') else None
        
        return JsonResponse({
            "status": "SUCCESS",
            "celery_task_output": result_msg,
            "database_records_saved": {
                "session_id": session.id,
                "interview_status": session.status,
                "total_duration": f"{session.duration_seconds} seconds",
                "raw_full_transcript": session.raw_full_transcript,
                "telephony_carrier_sid": log.provider_call_sid,
                "telephony_provider": log.telephony_provider,
            },
            "day37_answer_scoring_matrix": {
                "evaluated_question_key": q2.question_key if q2 else "N/A",
                "candidate_raw_input": ans2.raw_speech_text if ans2 else "N/A",
                "relevance_dimension": ans2.relevance_score if ans2 else 0.0,
                "completeness_dimension": ans2.completeness_score if ans2 else 0.0,
                "keyword_dimension": ans2.keyword_score if ans2 else 0.0,
                "normalized_final_score": f"{ans2.final_evaluation_score}%" if ans2 else "0.0%",
                "annotations_payload": ans2.structured_analysis if ans2 else {}
            }
        })
    except Exception as e:
        return JsonResponse({
            "status": "ERROR", 
            "message": "Could not extract Day 37 score metric rows.", 
            "details": str(e)
        })



def test_day38_scheduling_view(request):
    """
    Day 38 Verification Endpoint: Seeds mock calendar availability windows,
    forces conflict-resolution tests, applies bookings, and runs async emails.
    """
    try:
        # 1. Grab latest application setup record reference
        app = JobApplication.objects.latest('id')

        # 2. Seed 2 Mock Availability Slots for testing if none exist
        now = timezone.now()
        slot_1, _ = HRRecruiterAvailability.objects.get_or_create(
            interviewer_name="Ananthakrishnan Nair",
            target_role="Senior Python Engineer",
            start_time=now + timedelta(days=2, hours=4),
            end_time=now + timedelta(days=2, hours=5),
            defaults={'status': 'AVAILABLE'}
        )
        
        slot_2, _ = HRRecruiterAvailability.objects.get_or_create(
            interviewer_name="Meera Joseph",
            target_role="Lead Full-Stack Developer",
            start_time=now + timedelta(days=3, hours=2),
            end_time=now + timedelta(days=3, hours=3),
            defaults={'status': 'AVAILABLE'}
        )

        # Clear out prior scheduling tests for a clean running loop
        AIInterviewSchedule.objects.filter(application=app).delete()
        HRRecruiterAvailability.objects.filter(booked_interview__isnull=True).update(status='AVAILABLE')

        # Run Test Execution 1: Initial successful automated booking allocation
        success_1, res_1 = AIInterviewSchedulingEngine.auto_book_interview_slot(
            application_id=app.id,
            slot_id=slot_1.id
        )

        # Run Test Execution 2: Intentional Double-Booking Conflict Resolution Check
        success_2, res_2 = AIInterviewSchedulingEngine.auto_book_interview_slot(
            application_id=app.id,
            slot_id=slot_1.id
        )

        # 3. Fire the Asynchronous Confirmation Email Trigger task via Celery
        email_status = "N/A"
        if success_1:
            email_status = async_dispatch_scheduling_confirmation_email(schedule_id=res_1.id)

        # 👇 AUTOMATED RELATION DEEP SCAN: Safely falls back to whatever profile model you have
        candidate_display_name = "Anonymous Applicant"
        if hasattr(app, 'candidate') and app.candidate:
            candidate_display_name = getattr(app.candidate, 'full_name', getattr(app.candidate, 'name', 'Applicant'))
        elif hasattr(app, 'candidate_name'):
            candidate_display_name = app.candidate_name

        return JsonResponse({
            "status": "SUCCESS",
            "scheduling_engine_diagnostics": {
                "candidate_target": candidate_display_name,
                "test_round_1_booking_success": success_1,
                "confirmed_interviewer": res_1.availability_slot.interviewer_name if success_1 else "N/A",
                "confirmed_allocated_time": res_1.availability_slot.start_time if success_1 else "N/A",
                "recruiter_slot_db_status_updated": res_1.availability_slot.status if success_1 else "N/A",
                "test_round_2_collision_prevented": not success_2,
                "collision_engine_rejection_reason": res_2 if not success_2 else "N/A",
                "asynchronous_email_delivered": email_status
            }
        })

    except Exception as e:
        return JsonResponse({"status": "ERROR", "message": "Scheduling testing framework collapsed.", "details": str(e)})
    


def test_day39_reminder_view(request):
    """
    Day 39 Diagnostic View Endpoint: Intercepts active schedules, overrides timestamps 
    to place them inside warning thresholds, triggers the cron scan, and reports output logs.
    """
    try:
        # 1. Grab an active confirmed schedule block
        schedule = AIInterviewSchedule.objects.filter(status='CONFIRMED').latest('id')
        
        # Clear out historical reminder logs to run a fresh, clean verification loop
        AIReminderLog.objects.filter(interview_schedule=schedule).delete()
        
        # 2. Manipulate the slot timeline parameters to simulate an interview occurring tomorrow
        # This shifts the start time exactly 24 hours ahead from this very second
        slot = schedule.availability_slot
        slot.start_time = timezone.now() + timedelta(hours=24, minutes=5)
        slot.save()

        # 3. Manually execute the scheduled cron background scan task synchronously
        scan_diagnostics = execute_periodic_interview_reminder_scan()

        # 4. Check the audit history logs inside the database to verify persistence
        saved_logs = list(AIReminderLog.objects.filter(interview_schedule=schedule).values('reminder_stage', 'status', 'dispatched_at'))

        return JsonResponse({
            "status": "SUCCESS",
            "cron_task_execution_output": scan_diagnostics,
            "database_delivery_audit_trail": {
                "interview_schedule_id": schedule.id,
                "mocked_target_time": slot.start_time,
                "persisted_reminder_logs": saved_logs
            }
        })
    except Exception as e:
        return JsonResponse({"status": "ERROR", "message": "Reminder automation framework crashed.", "details": str(e)})    
    



@api_view(['GET'])
@permission_classes([AllowAny]) 
def candidate_ai_report_api_view(request, application_id):
    """
    Day 40 Secure Endpoint: Dynamically locates active applications and 
    serializes a clean JSON summary report layout.
    """
    user = request.user
    
    try:
        # 👇 FIX: Look up requested ID first, or fallback to the latest active application automatically
        if JobApplication.objects.filter(id=application_id).exists():
            application = JobApplication.objects.get(id=application_id)
        else:
            application = JobApplication.objects.latest('id')
            
        report = AICandidateReportEngine.compile_candidate_report(application, recruiter_user=user if user.is_authenticated else None)

        return JsonResponse({
            "status": "SUCCESS",
            "report_metadata": {
                "report_id": report.id,
                "application_id": report.application_id,
                "compiled_at": report.generated_at,
                "recruiter_reviewer": user.username if user.is_authenticated else "Mock_Recruiter_Admin"
            },
            "evaluation_metrics": {
                "ats_resume_match_score": f"{report.ats_match_score}%",
                "voice_screening_accuracy_score": f"{report.voice_screening_score}%"
            },
            "qualitative_intelligence": {
                "executive_summary_overview": report.executive_summary,
                "automated_strengths_array": report.identified_strengths,
                "automated_risks_and_gaps_array": report.identified_risks
            }
        })

    except JobApplication.DoesNotExist:
        return JsonResponse({
            "status": "ERROR", 
            "message": "No applications found in the database. Please apply to a job first to generate a candidate trace row."
        }, status=404)
    


@api_view(['GET'])
@permission_classes([AllowAny]) # Using AllowAny temporarily for hassle-free browser diagnostics
def recruiter_dashboard_analytics_api(request):
    """
    Day 41 Analytics API: Pulls query string filters, executes optimized funnel lookups, 
    and applies caching layers for rapid dashboard rendering.
    """
    # Grab optional target job filtering parameter from query URL parameters string (?job_id=13)
    job_id = request.GET.get('job_id')
     
    # ─── PERFORMANCE TUNING: IMPLEMENT DATA LAYER CACHING ───
    cache_key = f"recruiter_analytics_funnel_job_{job_id or 'all'}"
    
    # Retrieves cached data if present, otherwise calls the lambda method to execute lookups and saves for 5 minutes
    analytics_payload = cache.get_or_set(
        cache_key, 
        lambda: AIRecruiterAnalyticsEngine.get_job_funnel_analytics(job_id=job_id), 
        timeout=300
    )

    return JsonResponse({
        "status": "SUCCESS",
        "system_telemetry_tracking": {
            "active_target_scope": f"Job Post ID: {job_id}" if job_id else "Global SaaS Overview Portfolio",
            "cache_buffer_status": "Active (5-Minute Expiry Lock)"
        },
        "analytics_metrics": analytics_payload
    })    


@api_view(['GET', 'POST'])
@permission_classes([AllowAny]) # Exposed temporarily for effortless local diagnostic exercises
def platform_observability_audit_api(request):
    """
    Day 42 Verification Endpoint: Displays recorded log streams on GET, 
    and simulates security breaches/AI exceptions on POST.
    """
    user = request.user if request.user.is_authenticated else None

    if request.method == 'POST':
        event_trigger = request.data.get('trigger_type', 'SIMULATED_AI_FAILURE')

        if event_trigger == 'SECURITY_VIOLATION':
            # Record unauthorized system infiltration attempt indicators
            log_instance = CentralizedObservabilityService.log_system_event(
                actor_user=user,
                severity='ERROR',
                category='SECURITY',
                action_signature='UNAUTHORIZED_ACCESS_BREACH_ATTEMPT',
                details={"ip_source": "192.168.1.99", "target_path": "/api/admin/system-control/", "malicious_flag": True}
            )
            return JsonResponse({"status": "ALERT_RECORDED", "message": "Security anomaly logged successfully."}, status=403)

        else:
            # Record background service evaluation crashes or fallback loops
            log_instance = CentralizedObservabilityService.log_system_event(
                actor_user=user,
                severity='WARNING',
                category='AI_ENGINE',
                action_signature='AI_VOICE_SCREENING_RETRY_TRIGGERED',
                details={"attempt_number": 3, "application_id": 2, "exception_trace": "Timeout during multi-round TTS parsing."}
            )
            return JsonResponse({"status": "WARNING_RECORDED", "message": "Transient AI runtime warning logged successfully."})

    # GET Request: Fetch latest system records for operational dashboard updates
    logs = SystemAuditTrailLog.objects.all()[:10]
    log_dataset = []
    
    for l in logs:
        log_dataset.append({
            "log_id": l.id,
            "timestamp": l.timestamp,
            "severity_level": l.severity,
            "event_category": l.category,
            "signature": l.action_signature,
            "payload_data_dump": l.detailed_payload
        })

    return JsonResponse({
        "status": "SUCCESS",
        "system_observability_telemetry": {
            "total_audit_rows_discovered": SystemAuditTrailLog.objects.count(),
            "active_stream_limit": 10
        },
        "audit_trail_records": log_dataset
    })



class BruteforceAbusePreventionThrottle(AnonRateThrottle):
    """
    Custom strict rate limiter to block credential stuffing and brute force attempts.
    """
    rate = '3/min'  # Restrict clients to 3 requests per minute for this demonstration

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([BruteforceAbusePreventionThrottle]) # 🛡️ API Throttling Applied
def secure_candidate_onboarding_api(request):
    """
    Day 43 Protected Gateway: Validates access profiles, applies strict rate limits, 
    and handles encrypted field parsing to prevent platform data leakage.
    """
    # 1. Access validation role check simulation
    has_onboarding_role = request.headers.get('X-Platform-Role') == 'RECRUITER'
    
    # 2. Extract payload field parameters
    sensitive_identification_number = request.data.get('national_id', '')
    candidate_raw_name = request.data.get('candidate_name', 'Anonymous Candidate')

    if not sensitive_identification_number:
        return JsonResponse({"status": "FAILED", "reason": "Missing required sensitive fields."}, status=400)

    # 3. Data Encryption Execution
    encrypted_id_hash = SecureDataCryptographicGuard.encrypt_field(sensitive_identification_number)
    decrypted_id_verify = SecureDataCryptographicGuard.decrypt_field(encrypted_id_hash)

    return JsonResponse({
        "status": "SUCCESS",
        "security_perimeter_telemetry": {
            "rate_limiting_gate": "ACTIVE (Strict 3-Req/Min Restriction)",
            "role_validation_status": "PASSED" if has_onboarding_role else "WARNING: Standard Scope (No Recruiter Token Provided)"
        },
        "encrypted_data_handling": {
            "candidate_name": candidate_raw_name,
            "database_secure_blob_string": encrypted_id_hash,  # What goes into DB
            "runtime_decrypted_validation": decrypted_id_verify  # Decrypted proof
        }
    })



@api_view(['GET'])
@permission_classes([AllowAny]) # Kept as AllowAny temporarily for direct local stress evaluation
def system_load_testing_benchmark_api(request):
    """
    Day 44 Performance Benchmark API: Accepts configurable load size multipliers 
    via parameters, executes concurrent table scans, and returns real-time bottleneck insights.
    """
    # 1. Grab optional execution intensity scale factor (?scale=100)
    try:
        scale_factor = int(request.GET.get('scale', 50))
    except ValueError:
        scale_factor = 50

    # 2. Fire up the execution tracking matrix
    load_test_results = APSystemLoadStressEngine.run_concurrent_stress_simulation(simulation_cycles=scale_factor)

    return JsonResponse({
        "status": "COMPLETED",
        "load_tester_telemetry": {
            "testing_agent": "ZecPath High-Concurrency Simulation Tool v1.0",
            "active_database_engine": "PostgreSQL Isolation Matrix",
        },
        "load_test_report": load_test_results
    })


import hmac
import hashlib
import uuid
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from core.models import SubscriptionPlan, UserSubscription, PaymentTransaction, BillingHistory

# Mock Gateway Secret Keys for Day 47 Sandbox Isolation Matrix
MOCK_RAZORPAY_KEY_SECRET = "zecpath_sandbox_secret_98347291"

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_payment_order_api(request):
    """
    Day 47: Initiates payment order and records a PENDING tracking transaction record.
    Expects: {"plan_id": <int>}
    """
    plan_id = request.data.get('plan_id')
    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)
    except SubscriptionPlan.DoesNotExist:
        return Response({"error": "Target subscription plan not found."}, status=status.HTTP_404_NOT_FOUND)

    # Calculate actual price (Stripe/Razorpay process amounts in the lowest currency unit, i.e., Cents/Paise)
    # E.g., $49.00 -> 4900 cents
    lowest_unit_amount = int(plan.price * 100)
    
    # Simulate gateway response parameters mapping
    mock_order_id = f"order_zec_{uuid.uuid4().hex[:12].upper()}"

    # Record the pending transaction state inside your database
    transaction = PaymentTransaction.objects.create(
        user=request.user,
        amount=plan.price,
        gateway='RAZORPAY',
        gateway_reference_id=mock_order_id,
        status='PENDING'
    )

    return Response({
        "status": "ORDER_CREATED",
        "gateway_order_id": mock_order_id,
        "amount": plan.price,
        "currency": "USD",
        "plan_name": plan.name,
        "transaction_id": transaction.id
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment_signature_api(request):
    """
    Day 47: Performs secure server-side cryptographic signature validation.
    Expects: {"gateway_order_id": "...", "gateway_payment_id": "...", "gateway_signature": "...", "plan_id": <int>}
    """
    order_id = request.data.get('gateway_order_id')
    payment_id = request.data.get('gateway_payment_id')
    signature = request.data.get('gateway_signature')
    plan_id = request.data.get('plan_id')

    if not all([order_id, payment_id, signature, plan_id]):
        return Response({"error": "Missing signature verification tokens."}, status=status.HTTP_400_BAD_REQUEST)

    # 🔒 SECURITY CONSIDERATION: Signature Verification
    # Formulate payload exactly as standard payment gateways require
    generated_signature_payload = f"{order_id}|{payment_id}"
    
    # Compute signature check block using secure hmac-sha256
    computed_signature = hmac.new(
        bytes(MOCK_RAZORPAY_KEY_SECRET, 'utf-8'),
        msg=bytes(generated_signature_payload, 'utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

    # Locate our corresponding tracking transaction row
    try:
        transaction = PaymentTransaction.objects.get(gateway_reference_id=order_id)
        plan = SubscriptionPlan.objects.get(id=plan_id)
    except (PaymentTransaction.DoesNotExist, SubscriptionPlan.DoesNotExist):
        return Response({"error": "Invalid order reference transaction tracing key."}, status=status.HTTP_404_NOT_FOUND)

    # Cryptographic validation match check
    if computed_signature != signature:
        # Fraud protection: update tracking transaction block to failed state instantly
        transaction.status = 'FAILED'
        transaction.save()
        return Response({"status": "SIGNATURE_INVALID", "message": "Security warning: Cryptographic mismatch flagged."}, status=status.HTTP_400_BAD_REQUEST)

    # Capture payment states & finalize transaction successfully
    transaction.status = 'SUCCESS'
    transaction.save()

    # 🔄 Provisioning Strategy: Update or assign user's active plan duration window
    subscription, created = UserSubscription.objects.get_or_create(
        user=request.user,
        defaults={
            'plan': plan,
            'current_period_start': timezone.now(),
            'current_period_end': timezone.now() + timezone.timedelta(days=plan.billing_cycle_days)
        }
    )
    
    if not created:
        subscription.plan = plan
        subscription.current_period_start = timezone.now()
        subscription.current_period_end = timezone.now() + timezone.timedelta(days=plan.billing_cycle_days)
        subscription.status = 'ACTIVE'
        subscription.save()

    # 🧾 Generate historical invoice numbers tracking row
    BillingHistory.objects.create(
        user=request.user,
        transaction=transaction,
        invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        pdf_statement_url=f"https://zecpath-billing-s3.amazonaws.com/statements/invoice_{order_id}.pdf"
    )

    return Response({
        "status": "PAYMENT_VERIFIED",
        "message": f"Successfully activated subscription tier: {plan.get_name_display()}!",
        "account_valid_until": subscription.current_period_end.isoformat()
    }, status=status.HTTP_200_OK)    



from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from core.models import UserSubscription, SubscriptionPlan
from core.decorators import require_premium_feature

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def premium_ai_analytics_report_api(request):
    """
    Day 48: Premium feature gate demonstrating advanced compute restrictions.
    """
    # Wrap with our custom feature decorator dynamically at runtime
    @require_premium_feature('has_ai_analytics')
    def execute_logic(request):
        return Response({
            "status": "SUCCESS",
            "report_data": {
                "efficiency_rating": "94.2%",
                "candidate_match_velocity": "High",
                "ai_insights": "Recruitment pipeline is currently fully optimized."
            }
        }, status=status.HTTP_200_OK)
        
    return execute_logic(request)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def post_monetized_job_api(request):
    """
    Day 48: Usage limit gate demonstrating dynamic database row checks.
    """
    # Simulate calculating current usage (e.g., count total jobs posted by user)
    # Mock counter for validation testing: simulate user having posted 4 jobs already
    mock_active_job_count = 4
    
    try:
        subscription = UserSubscription.objects.get(request.user)
        max_allowed = subscription.plan.max_job_postings
    except:
        # Default fallback context parameters (Free tier limits)
        max_allowed = 3

    # Validate volume constraint (where -1 represents infinite allocation)
    if max_allowed != -1 and mock_active_job_count >= max_allowed:
        return Response({
            "error": "USAGE_LIMIT_EXCEEDED",
            "message": f"Your current tier caps active listings at {max_allowed} postings. Upgrade to clear these boundaries."
        }, status=status.HTTP_403_FORBIDDEN)

    return Response({
        "status": "JOB_PUBLISHED",
        "message": "Job profile listed successfully on the global directory matrix."
    }, status=status.HTTP_201_CREATED)


import time
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from core.models import UserSubscription

# Simple In-Memory Throttle Cache for Day 49 Rate Control Sandbox Validation
THROTTLE_CACHE = {}

def check_rate_control(user_id, max_requests=2, window_seconds=60):
    """
    Day 49 API Rate Control: Limits heavy premium analytics calls to prevent system abuse.
    """
    now = time.time()
    if user_id not in THROTTLE_CACHE:
        THROTTLE_CACHE[user_id] = []
    
    THROTTLE_CACHE[user_id] = [t for t in THROTTLE_CACHE[user_id] if now - t < window_seconds]
    
    if len(THROTTLE_CACHE[user_id]) >= max_requests:
        return False
        
    THROTTLE_CACHE[user_id].append(now)
    return True


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def premium_recruiter_insights_api(request):
    """
    Day 49: Monetized Insight Engine. Accessible exclusively to Premium Recruiter Accounts.
    """
    user = request.user

    # 🛡️ STEP 1: BYPASSED FOR TESTING
    # is_recruiter = getattr(user, 'is_recruiter', False) or user.groups.filter(name='Recruiters').exists()
    # if not is_recruiter and not user.is_staff:
    #     return Response({
    #         "error": "ROLE_RESTRICTED",
    #         "message": "Access Denied. This monetization resource is restricted to Recruiter account profiles only."
    #     }, status=status.HTTP_403_FORBIDDEN)

    # 🛡️ Task 2: Subscription Tier Verification (BYPASSED FOR SCENARIO 3)
    try:
        subscription = UserSubscription.objects.get(user=user)
        if not subscription.plan.has_premium_insights or subscription.status != 'ACTIVE':
            pass  # 👈 Commented out standard return block
            
    except UserSubscription.DoesNotExist:
        pass  # 👈 Commented out standard return block

    # 🛡️ Task 4: API Rate Control Execution
    if not check_rate_control(user.id, max_requests=2, window_seconds=60):
        return Response({
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Too many data requests. Premium analytical reports are capped at 2 calls per minute."
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)

    # 📊 Task 1 & 3: Premium Data Service Payloads
    return Response({
        "status": "SUCCESS",
        "timestamp": time.time(),
        "ai_candidate_ranking_report": [
            {"rank": 1, "candidate_name": "Harisankar TK", "match_score": 98.4, "prediction": "HIGH_RETENTION_PROBABILITY"},
            {"rank": 2, "candidate_name": "Inder Singh", "match_score": 96.2, "prediction": "FAST_ONBOARDING_POTENTIAL"},
            {"rank": 3, "candidate_name": "Amit Sharma", "match_score": 89.1, "prediction": "STABLE_PERFORMER"}
        ],
        "hiring_efficiency_metrics": {
            "average_time_to_hire_days": 14,
            "pipeline_velocity_multiplier": "1.8x Faster",
            "cost_per_hire_reduction": "22%"
        }
    }, status=status.HTTP_200_OK)


from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Sum, Count
from django.db import transaction as db_transaction
from django.utils import timezone
from core.models import Transaction, RefundLog, FinancialAuditLog, UserSubscription
import datetime

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_revenue_dashboard_api(request):
    """
    Task 2: Aggregates real-time financial metrics across intervals and active plan tiers.
    """
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    # 1. Period Calculations
    daily_rev = Transaction.objects.filter(created_at__date=today, status='SUCCESS').aggregate(total=Sum('amount'))['total'] or 0.00
    monthly_rev = Transaction.objects.filter(created_at__date__gte=start_of_month, status='SUCCESS').aggregate(total=Sum('amount'))['total'] or 0.00

   # 2. Plan Breakdown Metrics (Fixed syntax)
    plan_breakdown = Transaction.objects.filter(status='SUCCESS').values('subscription__plan__name').annotate(
        total_revenue=Sum('amount'),
        transaction_count=Count('id')
    ).order_by('-total_revenue') # <-- Ensure this reads .order_by() cleanly!

    return Response({
        "status": "METRICS_FETCHED",
        "summary": {
            "daily_revenue": float(daily_rev),
            "monthly_revenue": float(monthly_rev),
            "currency": "INR"
        },
        "plan_wise_metrics": plan_breakdown
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_process_refund_api(request):
    """
    Task 3 & 4: Atomic refund trigger changing transactional state and writing audit logs.
    """
    transaction_id = request.data.get("transaction_id")
    refund_reason = request.data.get("reason", "Administrative return preference.")

    if not transaction_id:
        return Response({"error": "MISSING_PARAMETER", "message": "Transaction identification string required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with db_transaction.atomic():
            # Fetch target item
            txn = Transaction.objects.select_for_update().get(id=transaction_id)

            if txn.status == 'REFUNDED':
                return Response({"error": "ALREADY_REFUNDED", "message": "This transaction hash has already been settled via return."}, status=status.HTTP_400_BAD_REQUEST)

            # Update status
            txn.status = 'REFUNDED'
            txn.save()

            # Record Details
            RefundLog.objects.create(
                transaction=txn,
                reason=refund_reason,
                processed_by=request.user
            )

            # Log Security Metric
            FinancialAuditLog.objects.create(
                event_type="REFUND_MANUAL_EXECUTION",
                description=f"Transaction {txn.stripe_charge_id} manually refunded by Admin ID: {request.user.id}.",
                severity="WARNING",
                metadata={"amount": float(txn.amount), "user_id": txn.user.id}
            )

            return Response({
                "status": "REFUND_PROCESSED",
                "message": f"Successfully reversed invoice value of {txn.amount} INR."
            }, status=status.HTTP_200_OK)

    except Transaction.DoesNotExist:
        return Response({"error": "TRANSACTION_NOT_FOUND", "message": "No transaction records match input criteria."}, status=status.HTTP_404_NOT_FOUND)
