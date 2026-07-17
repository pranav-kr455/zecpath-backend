from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.utils import timezone

from django.contrib.auth import get_user_model

# ==========================================
# 1. ROLE CONSTANTS SYSTEM
# ==========================================
class Roles(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'
    EMPLOYER = 'EMPLOYER', 'Employer'
    CANDIDATE = 'CANDIDATE', 'Candidate'


# ==========================================
# 2. CUSTOM USER MANAGER SYSTEM
# ==========================================
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        extra_fields.setdefault('role', Roles.CANDIDATE)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', Roles.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# ==========================================
# 3. CUSTOM USER MODEL
# ==========================================
class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CANDIDATE)
    
    # System Flags
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.email} ({self.role})"


# ==========================================
# 4. ATS PROFILE RELATIONS
# ==========================================
class Employer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='employer_profile')
    company_name = models.CharField(max_length=255, blank=True, null=True)
    domain = models.CharField(max_length=100, blank=True, null=True)  # e.g., FinTech, HealthCare
    company_size = models.PositiveIntegerField(blank=True, null=True)
    is_profile_verified = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # Soft delete logic

    def __str__(self):
        return self.company_name or f"Employer Profile for {self.user.email}"


def resume_upload_path(instance, filename):
    """
    Standardizes file names to prevent collisions.
    Saves files to: media/resumes/user_id/resume.ext
    """
    ext = filename.split('.')[-1]
    return f'resumes/user_{instance.user.id}/resume.{ext}'


class Candidate(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidate_profile')
    skills = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    experience = models.TextField(blank=True, null=True)
    expected_salary = models.DecimalField(decimal_places=2, max_digits=12, blank=True, null=True)
    
    # Media Target Field (Day 12)
    resume = models.FileField(upload_to=resume_upload_path, blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Candidate Profile for {self.user.email}"


# ==========================================
# 5. OPERATIONAL ATS ENTITIES (DAY 16 ENHANCED)
# ==========================================
class JobPost(models.Model):
    """
    Day 16 Enhanced: Database schema for tracking enterprise job listings.
    Includes relational foreign keys, operational choices, and indexed search optimization.
    """
    JOB_TYPE_CHOICES = [
        ('FULL_TIME', 'Full Time'),
        ('PART_TIME', 'Part Time'),
        ('CONTRACT', 'Contract'),
        ('REMOTE', 'Remote'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active / Accepting Applications'),
        ('PAUSED', 'Paused'),
        ('CLOSED', 'Closed'),
    ]

    employer_profile = models.ForeignKey(
        Employer, 
        on_delete=models.CASCADE, 
        related_name='job_posts'
    )
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    skills_required = models.TextField(help_text="Comma-separated list of required technical competencies")
    experience_years = models.PositiveIntegerField(default=0, help_text="Minimum experience required in years")
    location = models.CharField(max_length=150, default="Remote")
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='FULL_TIME')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        company = self.employer_profile.company_name or "Unknown Company"
        return f"{self.title} at {company} ({self.status})"


# ==========================================
# 6. JOB APPLICATION PIPELINE (DAY 18 ENHANCED)
# ==========================================
from django.db import models
from .models import JobPost, Candidate  # Ensuring your foreign key relations import cleanly

class JobApplication(models.Model):
    """
    Day 18 Complete Schema (Enhanced Day 25 & 28): Equipped with an ATS pipeline,
    duplicate prevention configurations, and high-performance system indices.
    """
    STATUS_CHOICES = [
        ('APPLIED', 'Applied / Pending Review'),
        ('REVIEWING', 'In Profile Screening'),
        ('INTERVIEW', 'Interview Phase Scheduled'),
        ('OFFER', 'Job Offer Extended'),
        ('REJECTED', 'Application Rejected'),
    ]

    job = models.ForeignKey(
        JobPost, 
        on_delete=models.CASCADE, 
        related_name='applications'
    )
    candidate_profile = models.ForeignKey(
        Candidate, 
        on_delete=models.CASCADE, 
        related_name='applications'
    )
    
    # Point-in-time document snapshot tracking
    resume_snapshot = models.FileField(
        upload_to="application_resumes_snapshots/", 
        null=True, 
        blank=True,
        help_text="Tracks the active candidate resume snapshot at the exact millisecond of submission."
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='APPLIED'
    )
    
    # 📈 Day 25: ATS Match Analytics Persistency
    ats_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00) # e.g., 85.50%

    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # 🛡️ STRIKE DUPLICATE PREVENTION: A candidate can only apply once to a specific JobPost
        unique_together = ('job', 'candidate_profile')
        
        # 📈 CORE RANKING ORDER: Automatically order metrics by highest matching ATS score, then latest date
        ordering = ['-ats_score', '-applied_at']
        
        # ⚡ DAY 28 PERFORMANCE OPTIMIZATION: Indexing fields frequently hit by filters or searches
        indexes = [
            models.Index(fields=['status'], name='idx_app_status'),
            models.Index(fields=['ats_score'], name='idx_app_ats_score'),
            models.Index(fields=['applied_at'], name='idx_app_applied_at'),
        ]

    def __str__(self):
        return f"{self.candidate_profile.user.email} -> {self.job.title} ({self.status})"    

class ApplicationAuditLog(models.Model):
    """
    Day 19: Immutable historical ledger capturing every single status transition 
    executed by hiring authorities inside the ATS pipeline matrix.
    """
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='audit_logs')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True, help_text="Optional reason or interview feedback details.")

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"App #{self.application.id}: {self.old_status} -> {self.new_status} at {self.changed_at}" 

# ==========================================
# 7. CANDIDATE PORTFOLIO UTILITIES (DAY 21)
# ==========================================
class SavedJob(models.Model):
    """
    Day 21: Bookmark system enabling candidates to save active job vacancies 
    to their personal dashboard portfolio before submitting a formal application.
    """
    candidate = models.ForeignKey(
        Candidate, 
        on_delete=models.CASCADE, 
        related_name='saved_jobs'
    )
    job = models.ForeignKey(
        JobPost, 
        on_delete=models.CASCADE, 
        related_name='saved_by_candidates'
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-saved_at']
        # Ensures a candidate cannot save the exact same job post multiple times
        unique_together = ('candidate', 'job')

    def __str__(self):
        return f"{self.candidate.user.email} bookmarked {self.job.title}"
    

class AdminActionLog(models.Model):
    """
    Day 22: Compliance ledger tracking administrative moderation actions 
    such as profile approvals, system blocks, and content takedowns.
    """
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_actions')
    action_type = models.CharField(max_length=50) # e.g., EMPLOYER_APPROVE, USER_BLOCK, JOB_REMOVED
    target_info = models.CharField(max_length=255) # e.g., "User: company@test.com" or "Job ID: 14"
    details = models.TextField(blank=True, null=True)
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-executed_at']

    def __str__(self):
        return f"{self.admin.email} executed {self.action_type} on {self.executed_at}"    




class AICallTracking(models.Model):
    STATUS_CHOICES = [
        ('ELIGIBLE', 'Eligible / Validation Clear'),
        ('QUEUED', 'Call Queued in Pipeline'),
        ('IN_PROGRESS', 'Outbound Dialing Active'),
        ('COMPLETED', 'Screening Completed successfully'),
        ('FAILED', 'Handshake Failure / Carrier Dropped'),
        ('BLOCKED', 'Outside Permissible Business Hours'),
    ]

    application = models.OneToOneField('JobApplication', on_delete=models.CASCADE, related_name='ai_call_tracking')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ELIGIBLE')
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    scheduled_window_start = models.DateTimeField(default=timezone.now)
    last_attempt = models.DateTimeField(null=True, blank=True)
    execution_logs = models.TextField(default="Engine initialized.")

    def __str__(self):
        return f"App {self.application.id} - Call Status: {self.status}"      


class AIInterviewSession(models.Model):
    """
    Tracks the macro-state of a live AI telephonic screening interview.
    """
    SESSION_STATUS = [
        ('INITIATED', 'Trunk Line Established'),
        ('RINGING', 'Device Alerting Carrier'),
        ('CONNECTED', 'Candidate Answered / Live Dialogue'),
        ('COMPLETED', 'Interview Finalized Normally'),
        ('ABANDONED', 'Candidate Hung Up Early'),
        ('NO_ANSWER', 'Carrier Timeout / Voice Mail Hit'),
    ]

    application = models.ForeignKey('JobApplication', on_delete=models.CASCADE, related_name='ai_sessions')
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='INITIATED')
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    overall_sentiment_score = models.FloatField(null=True, blank=True) # Normalized scale (-1.0 to 1.0)
    raw_full_transcript = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Session {self.id} - App {self.application_id} ({self.status})"


class AIQuestion(models.Model):
    """
    Stores individual contextual questions spoken by the AI persona.
    """
    session = models.ForeignKey(AIInterviewSession, on_delete=models.CASCADE, related_name='questions')
    question_key = models.CharField(max_length=100) # e.g., 'django_middleware_check'
    question_text = models.TextField()
    sequence_order = models.PositiveIntegerField(default=1)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['sequence_order']

    def __str__(self):
        return f"Q{self.sequence_order} in Session {self.session.id}"



class AIAnswer(models.Model):
    """
    Day 37 Enhanced: Stores speech-to-text outputs, discrete multi-dimensional
    analytical scores, keyword verification targets, and normalized aggregate calculations.
    """
    question = models.OneToOneField('AIQuestion', on_delete=models.CASCADE, related_name='answer')
    raw_speech_text = models.TextField()
    confidence_score = models.FloatField(default=1.0) # Speech-to-text model confidence
    
    # Granular Scoring Pillars (Values range from 0.00 to 10.00)
    relevance_score = models.FloatField(default=0.0)    # How well did they address the prompt?
    completeness_score = models.FloatField(default=0.0) # Did they answer all parts of the question?
    keyword_score = models.FloatField(default=0.0)    # Did they utilize necessary professional terms?
    
    # Normalized Total Evaluation Score (Scaled from 0.00% to 100.00%)
    final_evaluation_score = models.FloatField(default=0.0)
    
    # Complex JSON Annotation payload repository
    structured_analysis = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Answer for Q_ID {self.question_id} - Score: {self.final_evaluation_score}%"

class AICallLog(models.Model):
    """
    Audit-ready logging engine mapping low-level signaling infrastructure meta arrays.
    """
    session = models.OneToOneField(AIInterviewSession, on_delete=models.CASCADE, related_name='call_log')
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='triggered_ai_calls')
    telephony_provider = models.CharField(max_length=50, default='Twilio')
    provider_call_sid = models.CharField(max_length=100, unique=True, db_index=True) # Core Carrier ID string
    sip_response_code = models.IntegerField(null=True, blank=True) # e.g., 200 OK, 486 Busy
    trigger_reason = models.CharField(max_length=255, default="Automated threshold system shortlist rule match.")
    ip_address = models.GenericIPAddressField(null=True, blank=True) # Trigger source network identifier
    carrier_logs = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Audit Log - Sid {self.provider_call_sid}"          



class AIQuestionTemplate(models.Model):
    """
    Stores reusable structural evaluation prompts classified by categories 
    and difficulty tiers for runtime state building.
    """
    CATEGORY_CHOICES = [
        ('INTRO', 'Introduction & Background'),
        ('EXPERIENCE', 'Professional Experience Audit'),
        ('SKILLS', 'Role-Specific Technical Competency'),
        ('AVAILABILITY', 'Availability & Shift Logistics'),
        ('SALARY', 'Compensation & Salary Expectations'),
    ]

    role_type = models.CharField(max_length=100, default="Python Full Stack Developer")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    question_key = models.CharField(max_length=100, unique=True) # e.g., 'django_middleware_exp'
    template_text = models.TextField() # e.g., "Walk me through how you would configure {keyword}..."
    sequence_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sequence_order']

    def __str__(self):
        return f"[{self.category}] {self.question_key} (Order: {self.sequence_order})"



class HRRecruiterAvailability(models.Model):
    """
    Tracks availability windows opened by specific internal HR recruiters or technical interviewers.
    """
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('BOOKED', 'Booked'),
        ('BLOCKED', 'Blocked'),
    ]
    interviewer_name = models.CharField(max_length=150)
    target_role = models.CharField(max_length=100, default="Technical Interviewer")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')

    def __str__(self):
        return f"{self.interviewer_name} ({self.target_role}) - {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class AIInterviewSchedule(models.Model):
    """
    Stores finalized automation bookings connecting applications, time slots, and confirmation states.
    """
    STATUS_CHOICES = [
        ('CONFIRMED', 'Confirmed'),
        ('RESCHEDULED', 'Rescheduled'),
        ('CANCELLED', 'Cancelled'),
    ]
    application = models.OneToOneField('JobApplication', on_delete=models.CASCADE, related_name='scheduled_interview')
    availability_slot = models.OneToOneField(HRRecruiterAvailability, on_delete=models.PROTECT, related_name='booked_interview')
    scheduled_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED')
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Interview for App #{self.application_id} on {self.availability_slot.start_time}"



class AIReminderLog(models.Model):
    """
    Day 39: Tracks automated reminder lifecycle stages, recording successful 
    dispatches and capturing system execution exceptions to ensure zero double-sends.
    """
    STAGE_CHOICES = [
        ('24_HOUR', '24 Hours Before Alert'),
        ('1_HOUR', '1 Hour Final Alert'),
    ]
    STATUS_CHOICES = [
        ('SUCCESS', 'Delivered successfully'),
        ('FAILED', 'Transmission Failure'),
    ]
    
    interview_schedule = models.ForeignKey('AIInterviewSchedule', on_delete=models.CASCADE, related_name='reminder_logs')
    reminder_stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    dispatched_at = models.DateTimeField(auto_now_add=True)
    error_details = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('interview_schedule', 'reminder_stage') # Enforces unique stage locks

    def __str__(self):
        return f"Schedule #{self.interview_schedule_id} - Stage: {self.reminder_stage} ({self.status})"        



User = get_user_model()

class AICandidateEvaluationReport(models.Model):
    """
    Day 40: Aggregates historical multi-round testing metrics, providing structured
    intelligence summaries and risk evaluations exclusively for recruiter review.
    """
    application = models.OneToOneField('JobApplication', on_delete=models.CASCADE, related_name='evaluation_report')
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, limit_choices_to={'role': 'EMPLOYER'})
    
    # Aggregated Quantitative Data
    ats_match_score = models.FloatField(default=0.0)
    voice_screening_score = models.FloatField(default=0.0)
    
    # Structural Text Intelligence
    executive_summary = models.TextField()
    identified_strengths = models.JSONField(default=list)  # List of strong technical points
    identified_risks = models.JSONField(default=list)      # List of gaps or yellow flags
    
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AI Report: App #{self.application_id} - ATS: {self.ats_match_score}%"        



User = get_user_model()
class SystemAuditTrailLog(models.Model):
    """
    Day 42 Governance Model: Centralized ledger capturing user, admin, 
    and background AI engine state interactions for production observability.
    """
    LOG_SEVERITY_CHOICES = [
        ('INFO', 'Information Log'),
        ('WARNING', 'Operational Warning / Retry'),
        ('ERROR', 'System Exception / Security Breach Attempt'),
    ]
    
    ACTION_CATEGORY_CHOICES = [
        ('USER_ACTION', 'Standard Candidate/Recruiter Interaction'),
        ('ADMIN_ACTION', 'Platform Governance Setting Updates'),
        ('AI_ENGINE', 'Automated Profiling & Voice Telemetry Evaluations'),
        ('SECURITY', 'Authentication & Access Controls Tracking'),
    ]

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs_triggered')
    severity = models.CharField(max_length=10, choices=LOG_SEVERITY_CHOICES, default='INFO')
    category = models.CharField(max_length=15, choices=ACTION_CATEGORY_CHOICES, default='USER_ACTION')
    action_signature = models.CharField(max_length=255)  # Brief signature identifier (e.g., 'JOB_APPLICATION_SUBMITTED')
    detailed_payload = models.JSONField(default=dict)   # Captures parameters, IPs, or stack trace indicators
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "System Audit Trail Log"
        verbose_name_plural = "System Audit Trail Logs"

    def __str__(self):
        return f"[{self.severity}][{self.category}] {self.action_signature} at {self.timestamp}"        



from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

# ==========================================
# (Keep your Custom UserManager and User Model classes here exactly as they are)
# ==========================================

class SubscriptionPlan(models.Model):
    """
    Day 46 & Day 49: Core Catalog table for available SaaS payment tiers.
    """
    TIER_CHOICES = [
        ('FREE', 'Free Tier'),
        ('PRO', 'Pro Professional Tier'),
        ('ENTERPRISE', 'Enterprise Suite'),
    ]
    name = models.CharField(max_length=50, choices=TIER_CHOICES, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    billing_cycle_days = models.IntegerField(default=30)
    max_job_postings = models.IntegerField(default=3)
    has_ai_analytics = models.BooleanField(default=False)
    has_voice_screening = models.BooleanField(default=False)
    
    # Day 49: Monetization Insight engine flag integrated seamlessly here!
    has_premium_insights = models.BooleanField(default=False)  
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_name_display()} (${self.price})"


class UserSubscription(models.Model):
    """
    Day 46: Tracks an active user's assigned tier and validity window.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active Subscription'),
        ('PAST_DUE', 'Payment Overdue Gracetrack'),
        ('CANCELLED', 'Cancelled Plan Account'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscribers')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_valid(self):
        return self.status == 'ACTIVE' and self.current_period_end > timezone.now()

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.status})"


class PaymentTransaction(models.Model):
    """
    Day 46: Logs raw transactional records mapping to external checkout tokens.
    """
    GATEWAY_CHOICES = [
        ('STRIPE', 'Stripe Gateway Engine'),
        ('RAZORPAY', 'Razorpay Local Processing'),
        ('MANUAL', 'Administrative Override'),
    ]
    TXN_STATUS = [
        ('SUCCESS', 'Transaction Completed Successfully'),
        ('FAILED', 'Transaction Declined/Aborted'),
        ('PENDING', 'Awaiting Webhook Confirmation'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    gateway = models.CharField(max_length=15, choices=GATEWAY_CHOICES, default='STRIPE')
    gateway_reference_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    status = models.CharField(max_length=15, choices=TXN_STATUS, default='PENDING')
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TXN-{self.id} - {self.user.username} (${self.amount}) - {self.status}"


class BillingHistory(models.Model):
    """
    Day 46: Legal ledger record used to render invoice listings for recruiters.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices')
    transaction = models.OneToOneField(PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_number = models.CharField(max_length=100, unique=True)
    issued_date = models.DateTimeField(default=timezone.now)
    pdf_statement_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"INV-{self.invoice_number} for {self.user.username}"


from django.db import models
from django.conf import settings
from core.models import UserSubscription

class Transaction(models.Model):
    """
    Main ledger tracking all incoming payments and state changes.
    """
    STATUS_CHOICES = [
        ('SUCCESS', 'Payment Completed'),
        ('FAILED', 'Payment Failed'),
        ('REFUNDED', 'Fully Refunded'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='transactions')
    subscription = models.ForeignKey(UserSubscription, on_delete=models.SET_NULL, null=True, blank=True)
    stripe_charge_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Txn {self.stripe_charge_id} - {self.amount} {self.currency}"


class RefundLog(models.Model):
    """
    Tracks administrative refund triggers and reference reasons.
    """
    transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name='refund_details')
    reason = models.TextField()
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='issued_refunds')
    refunded_at = models.DateTimeField(auto_now_add=True)


class FinancialAuditLog(models.Model):
    """
    Security ledger logging failures, manual overrides, or suspicious velocities.
    """
    SEVERITY_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Suspicious Activity'),
        ('CRITICAL', 'Payment Failure / Systemic Risk'),
    ]
    event_type = models.CharField(max_length=100) # e.g., "PAYMENT_VELOCITY_SPIKE", "REFUND_EXECUTION"
    description = models.TextField()
    severity = models.CharField(max_length=15, choices=SEVERITY_CHOICES, default='INFO')
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)        