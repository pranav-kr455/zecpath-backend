from django.http import JsonResponse, HttpResponse
from django.urls import path, re_path
from rest_framework import status
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

from .serializers import MyTokenObtainPairSerializer
from .models import AIInterviewSession
from . import views

# Explicit View Component Matrix Ingestion
from .views import (
    EmployerStatusUpdateView,
    EmployerDashboardAnalyticsView, 
    EmployerCandidatePipelineListView,
    CandidateDashboardOverviewView, 
    CandidateJobRecommendationsView,
    CandidateSaveJobToggleView,
    SignUpView, 
    EmployerJobCreateView,  
    EmployerJobDetailView,  
    CandidateApplyView, 
    CandidateApplicationHistoryView,
    AdminSystemControlView, 
    EmployerProfileDetailView, 
    CandidateProfileDetailView,
    JobPostListView,
    AdminPlatformStatsView, 
    AdminUserModerationView,
    ResumeParsingExtractionView,
    ResumeSkillExtractionView,
    JobATSScoringAndRankingView,
    AutomatedShortlistingView,
    OptimizedHRDashboardView,
    platform_observability_audit_api,
    recruiter_dashboard_analytics_api,
    secure_candidate_onboarding_api,
    system_load_testing_benchmark_api,
    test_day34_storage_view,
    # 📁 DAY 53 INGESTION: Import the view function or class that handles the file upload
    # (Update this line if your view name matches something else, like ResumeUploadView.as_view())
    resume_upload_api_view 
)

# ==========================================
# CUSTOM TOKEN VIEW WRAPPER
# ==========================================
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Overrides the default SimpleJWT login view to apply our custom serializer
    which injects the user's role into the JWT claims payload.
    """
    serializer_class = MyTokenObtainPairSerializer


# ==========================================
# GLOBAL ROUTING EXCEPTION HANDLER
# ==========================================
def global_404_handler(request, exception=None):
    """
    Intercepts core Django framework routing failures and forces them 
    into our uniform corporate JSON error response layout.
    """
    return JsonResponse(
        {
            "success": False,
            "error": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "The requested URL path was not found on this server.",
                "details": None
            }
        },
        status=status.HTTP_404_NOT_FOUND
    )


# ==========================================
# EXTRA DEBUG CODES (TEMPORARY DEV ONLY)
# ==========================================
def debug_database_view(request):
    try:
        session = AIInterviewSession.objects.latest('id')
        log = session.call_log
        question = session.questions.first()
        
        output = f"""
        <h1>=== INTERVIEW SESSION #{session.id} ===</h1>
        <p><b>Status:</b> {session.status} | <b>Duration:</b> {session.duration_seconds}s</p>
        <p><b>Transcript Output:</b><br>{session.raw_full_transcript.replace('\n', '<br>')}</p>
        
        <h2>=== TELEPHONY AUDIT TRAIL ===</h2>
        <p><b>Carrier Provider:</b> {log.telephony_provider}</p>
        <p><b>Carrier Call SID:</b> {log.provider_call_sid}</p>
        
        <h2>=== DIALOGUE INGESTION MATRIX ===</h2>
        <p><b>AI Prompt:</b> {question.question_text}</p>
        <p><b>Candidate Response:</b> {question.answer.raw_speech_text}</p>
        <p><b>Analysis Payload:</b> {question.answer.structured_analysis}</p>
        """
        return HttpResponse(output)
    except Exception as e:
        return HttpResponse(f"Error querying data: {str(e)}")


# ==========================================
# UNIFIED URL ROUTING MATRIX
# ==========================================
urlpatterns = [
    # Infrastructure Identity Paths
    path('auth/signup/', SignUpView.as_view(), name='api_signup'),
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Profile Management Gateways
    path('profile/employer/', EmployerProfileDetailView.as_view(), name='employer_profile'),
    path('profile/candidate/', CandidateProfileDetailView.as_view(), name='candidate_profile'),

    # RBAC Isolated Operational Paths (Day 18 Synchronized)
    path('jobs/create/', EmployerJobCreateView.as_view(), name='employer_create_job'),
    path('jobs/<int:pk>/', EmployerJobDetailView.as_view(), name='employer_job_detail'), 
    
    # Job Application Actions & Pipeline Tracking
    path('jobs/apply/', CandidateApplyView.as_view(), name='candidate_apply_job'),
    path('portfolio/applications/', CandidateApplicationHistoryView.as_view(), name='candidate_applications_history'),
    
    # System & Discovery Search
    path('admin/system/', AdminSystemControlView.as_view(), name='admin_system_control'),
    path('jobs/search/', JobPostListView.as_view(), name='job_search_list'),
    path('applications/<int:pk>/status/', EmployerStatusUpdateView.as_view(), name='employer_ats_status_update'),

    # Day 20: Employer SaaS Dashboard Modules
    path('dashboard/analytics/', EmployerDashboardAnalyticsView.as_view(), name='employer_dashboard_analytics'),
    path('dashboard/pipeline/', EmployerCandidatePipelineListView.as_view(), name='employer_candidate_pipeline'),
    
    path('candidate/dashboard/', CandidateDashboardOverviewView.as_view(), name='candidate_dashboard_overview'),
    path('candidate/recommendations/', CandidateJobRecommendationsView.as_view(), name='candidate_job_recommendations'),
    path('jobs/<int:job_id>/save/', CandidateSaveJobToggleView.as_view(), name='candidate_save_job_toggle'),

    # Day 22: Admin Governance & Control Panel Modules
    path('admin/stats/', AdminPlatformStatsView.as_view(), name='admin_platform_stats'),
    path('admin/users/<int:user_id>/moderate/', AdminUserModerationView.as_view(), name='admin_user_moderation'),
    
    # Day 23 & 24: Document Intelligence & NER Extraction Routes
    path('candidate/resume/parse/', ResumeParsingExtractionView.as_view(), name='candidate_resume_parse'),
    path('candidate/resume/extract-intel/', ResumeSkillExtractionView.as_view(), name='candidate_resume_extract_intel'),
    
    # Day 25 & 26: ATS Match Processing & Automated Shortlisting Workflow
    path('jobs/<int:job_id>/ats-score/', JobATSScoringAndRankingView.as_view(), name='job_ats_score_evaluation'),
    path('jobs/<int:job_id>/apply-automated/', AutomatedShortlistingView.as_view(), name='job_apply_automated_workflow'),
    
    # Day 28: Performance Optimization & Scaling Dashboard API Route
    path('hr/dashboard-optimized/', OptimizedHRDashboardView.as_view(), name='hr_dashboard_optimized'),

    # =========================================================================
    # EXPERIMENTAL ENGINEERING ENDPOINTS (TESTING SUITES)
    # =========================================================================
    path('debug-db/', debug_database_view, name='debug_db_view'),
    path('test-day34/', test_day34_storage_view, name='test-day34'),
    path('test-day38/', views.test_day38_scheduling_view, name='test_day38'),
    path('test-day39/', views.test_day39_reminder_view, name='test_day39'),
    path('applications/<int:application_id>/ai-report/', views.candidate_ai_report_api_view, name='candidate_ai_report'),
    
    path('hr/analytics/funnel/', recruiter_dashboard_analytics_api, name='recruiter_funnel_analytics'),
    path('system/observability/audit/', platform_observability_audit_api, name='platform_audit_observability'),
    path('security/hardened-onboarding/', secure_candidate_onboarding_api, name='secure_onboarding_gateway'),
    path('system/performance/stress-test/', system_load_testing_benchmark_api, name='system_load_stress_test'),

    path('payment/checkout/create-order/', views.create_payment_order_api, name='payment_create_order'),
    path('payment/checkout/verify-signature/', views.verify_payment_signature_api, name='payment_verify_signature'),

    path('billing/premium/ai-reports/', views.premium_ai_analytics_report_api, name='premium_ai_reports'),
    path('billing/jobs/post/', views.post_monetized_job_api, name='post_monetized_job'),
    path('billing/premium/recruiter-insights/', views.premium_recruiter_insights_api, name='premium_recruiter_insights'),

    path('admin/finance/dashboard/', views.admin_revenue_dashboard_api, name='admin_finance_dashboard'),
    path('admin/finance/refund/', views.admin_process_refund_api, name='admin_finance_refund'),

    # =========================================================================
    # DAY 53: NEW RESUME STORAGE UPLOAD GATEWAY
    # =========================================================================
    # Note: If your view is a Class-Based View, use: resume_upload_api_view.as_view()
    path('candidate/resume/upload/', resume_upload_api_view, name='candidate_resume_upload'),

    # =========================================================================
    # CATCH-ALL ROUTE (CRITICAL: MUST STAY AT THE ABSOLUTE BOTTOM)
    # =========================================================================
    re_path(r'^.*$', global_404_handler),
]