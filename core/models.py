from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.utils import timezone


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
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    role = models.CharField(max_length=20, choices=Roles.choices, default=Roles.CANDIDATE, db_index=True)
    
    # System Flags
    is_active = models.BooleanField(default=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        indexes = [
            models.Index(fields=['is_active', 'role'], name='idx_user_active_role'),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"


# ==========================================
# 4. ATS PROFILE RELATIONS
# ==========================================
class Employer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='employer_profile',
        db_index=True
    )
    company_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    domain = models.CharField(max_length=100, blank=True, null=True)
    company_size = models.PositiveIntegerField(blank=True, null=True)
    is_profile_verified = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_deleted', 'company_name'], name='idx_emp_deleted_name'),
        ]

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
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='candidate_profile',
        db_index=True
    )
    skills = models.TextField(blank=True, null=True)
    education = models.TextField(blank=True, null=True)
    experience = models.TextField(blank=True, null=True)
    expected_salary = models.DecimalField(decimal_places=2, max_digits=12, blank=True, null=True)
    
    resume = models.FileField(upload_to=resume_upload_path, blank=True, null=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_deleted', 'user'], name='idx_cand_deleted_user'),
        ]

    def __str__(self):
        return f"Candidate Profile for {self.user.email}"


# ==========================================
# 5. OPERATIONAL ATS ENTITIES (DAY 16 & 54 OPTIMIZED)
# ==========================================
class JobPost(models.Model):
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
        related_name='job_posts',
        db_index=True
    )
    
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField()
    skills_required = models.TextField(help_text="Comma-separated list of required technical competencies")
    experience_years = models.PositiveIntegerField(default=0, help_text="Minimum experience required in years")
    location = models.CharField(max_length=150, default="Remote", db_index=True)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='FULL_TIME')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)
    salary = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='idx_job_status_created'),
            models.Index(fields=['location', 'status'], name='idx_job_loc_status'),
            models.Index(fields=['job_type', 'status'], name='idx_job_type_status'),
        ]

    def __str__(self):
        company = self.employer_profile.company_name or "Unknown Company"
        return f"{self.title} at {company} ({self.status})"


# ==========================================
# 6. JOB APPLICATION PIPELINE (DAY 18, 28 & 54 OPTIMIZED)
# ==========================================
class JobApplication(models.Model):
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
        related_name='applications',
        db_index=True
    )
    candidate_profile = models.ForeignKey(
        Candidate, 
        on_delete=models.CASCADE, 
        related_name='applications',
        db_index=True
    )
    
    resume_snapshot = models.FileField(
        upload_to="application_resumes_snapshots/", 
        null=True, 
        blank=True,
        help_text="Tracks the active candidate resume snapshot at the exact millisecond of submission."
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='APPLIED',
        db_index=True
    )
    
    ats_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, db_index=True)

    applied_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('job', 'candidate_profile')
        ordering = ['-ats_score', '-applied_at']
        
        indexes = [
            models.Index(fields=['status', '-ats_score'], name='idx_app_status_ats'),
            models.Index(fields=['job', 'status'], name='idx_app_job_status'),
            models.Index(fields=['candidate_profile', 'status'], name='idx_app_cand_status'),
            models.Index(fields=['-applied_at'], name='idx_app_applied_desc'),
        ]

    def __str__(self):
        return f"{self.candidate_profile.user.email} -> {self.job.title} ({self.status})"    


class ApplicationAuditLog(models.Model):
    application = models.ForeignKey(JobApplication, on_delete=models.CASCADE, related_name='audit_logs', db_index=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, db_index=True)
    
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    notes = models.TextField(blank=True, null=True, help_text="Optional reason or interview feedback details.")

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['application', '-changed_at'], name='idx_audit_app_date'),
        ]

    def __str__(self):
        return f"App #{self.application.id}: {self.old_status} -> {self.new_status} at {self.changed_at}" 


# ==========================================
# 7. CANDIDATE PORTFOLIO UTILITIES & ADMIN LOGS
# ==========================================
class SavedJob(models.Model):
    candidate = models.ForeignKey(
        Candidate, 
        on_delete=models.CASCADE, 
        related_name='saved_jobs',
        db_index=True
    )
    job = models.ForeignKey(
        JobPost, 
        on_delete=models.CASCADE, 
        related_name='saved_by_candidates',
        db_index=True
    )
    saved_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-saved_at']
        unique_together = ('candidate', 'job')
        indexes = [
            models.Index(fields=['candidate', '-saved_at'], name='idx_saved_cand_date'),
        ]

    def __str__(self):
        return f"{self.candidate.user.email} bookmarked {self.job.title}"
    

class AdminActionLog(models.Model):
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='admin_actions', db_index=True)
    action_type = models.CharField(max_length=50, db_index=True)
    target_info = models.CharField(max_length=255)
    details = models.TextField(blank=True, null=True)
    executed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-executed_at']
        indexes = [
            models.Index(fields=['admin', '-executed_at'], name='idx_admin_action_date'),
        ]

    def __str__(self):
        return f"{self.admin.email} executed {self.action_type} on {self.executed_at}"    


# ==========================================
# 8. AI INTERVIEW & TELEPHONY MODULES
# ==========================================
class AICallTracking(models.Model):
    STATUS_CHOICES = [
        ('ELIGIBLE', 'Eligible / Validation Clear'),
        ('QUEUED', 'Call Queued in Pipeline'),
        ('IN_PROGRESS', 'Outbound Dialing Active'),
        ('COMPLETED', 'Screening Completed successfully'),
        ('FAILED', 'Handshake Failure / Carrier Dropped'),
        ('BLOCKED', 'Outside Permissible Business Hours'),
    ]

    application = models.OneToOneField('JobApplication', on_delete=models.CASCADE, related_name='ai_call_tracking', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ELIGIBLE', db_index=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    scheduled_window_start = models.DateTimeField(default=timezone.now, db_index=True)
    last_attempt = models.DateTimeField(null=True, blank=True)
    execution_logs = models.TextField(default="Engine initialized.")

    class Meta:
        indexes = [
            models.Index(fields=['status', 'scheduled_window_start'], name='idx_aicall_status_sched'),
        ]

    def __str__(self):
        return f"App {self.application.id} - Call Status: {self.status}"      


class AIInterviewSession(models.Model):
    SESSION_STATUS = [
        ('INITIATED', 'Trunk Line Established'),
        ('RINGING', 'Device Alerting Carrier'),
        ('CONNECTED', 'Candidate Answered / Live Dialogue'),
        ('COMPLETED', 'Interview Finalized Normally'),
        ('ABANDONED', 'Candidate Hung Up Early'),
        ('NO_ANSWER', 'Carrier Timeout / Voice Mail Hit'),
    ]

    application = models.ForeignKey('JobApplication', on_delete=models.CASCADE, related_name='ai_sessions', db_index=True)
    status = models.CharField(max_length=20, choices=SESSION_STATUS, default='INITIATED', db_index=True)
    started_at = models.DateTimeField(default=timezone.now, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    overall_sentiment_score = models.FloatField(null=True, blank=True)
    raw_full_transcript = models.TextField(blank=True, default="")

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['application', 'status'], name='idx_aisess_app_status'),
        ]

    def __str__(self):
        return f"Session {self.id} - App {self.application_id} ({self.status})"


class AIQuestion(models.Model):
    session = models.ForeignKey(AIInterviewSession, on_delete=models.CASCADE, related_name='questions', db_index=True)
    question_key = models.CharField(max_length=100)
    question_text = models.TextField()
    sequence_order = models.PositiveIntegerField(default=1)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['sequence_order']
        indexes = [
            models.Index(fields=['session', 'sequence_order'], name='idx_aiq_session_seq'),
        ]

    def __str__(self):
        return f"Q{self.sequence_order} in Session {self.session.id}"


class AIAnswer(models.Model):
    question = models.OneToOneField('AIQuestion', on_delete=models.CASCADE, related_name='answer', db_index=True)
    raw_speech_text = models.TextField()
    confidence_score = models.FloatField(default=1.0)
    
    # Granular Scoring Pillars
    relevance_score = models.FloatField(default=0.0)
    completeness_score = models.FloatField(default=0.0)
    keyword_score = models.FloatField(default=0.0)
    
    final_evaluation_score = models.FloatField(default=0.0, db_index=True)
    structured_analysis = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Answer for Q_ID {self.question_id} - Score: {self.final_evaluation_score}%"


class AICallLog(models.Model):
    session = models.OneToOneField(AIInterviewSession, on_delete=models.CASCADE, related_name='call_log', db_index=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='triggered_ai_calls', db_index=True)
    telephony_provider = models.CharField(max_length=50, default='Twilio')
    provider_call_sid = models.CharField(max_length=100, unique=True, db_index=True)
    sip_response_code = models.IntegerField(null=True, blank=True)
    trigger_reason = models.CharField(max_length=255, default="Automated threshold system shortlist rule match.")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    carrier_logs = models.TextField(blank=True, default="")

    def __str__(self):
        return f"Audit Log - Sid {self.provider_call_sid}"          


class AIQuestionTemplate(models.Model):
    CATEGORY_CHOICES = [
        ('INTRO', 'Introduction & Background'),
        ('EXPERIENCE', 'Professional Experience Audit'),
        ('SKILLS', 'Role-Specific Technical Competency'),
        ('AVAILABILITY', 'Availability & Shift Logistics'),
        ('SALARY', 'Compensation & Salary Expectations'),
    ]

    role_type = models.CharField(max_length=100, default="Python Full Stack Developer", db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    question_key = models.CharField(max_length=100, unique=True, db_index=True)
    template_text = models.TextField()
    sequence_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sequence_order']
        indexes = [
            models.Index(fields=['role_type', 'category'], name='idx_tmpl_role_cat'),
        ]

    def __str__(self):
        return f"[{self.category}] {self.question_key} (Order: {self.sequence_order})"


class HRRecruiterAvailability(models.Model):
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('BOOKED', 'Booked'),
        ('BLOCKED', 'Blocked'),
    ]
    interviewer_name = models.CharField(max_length=150)
    target_role = models.CharField(max_length=100, default="Technical Interviewer")
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE', db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'start_time'], name='idx_avail_status_start'),
        ]

    def __str__(self):
        return f"{self.interviewer_name} ({self.target_role}) - {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class AIInterviewSchedule(models.Model):
    STATUS_CHOICES = [
        ('CONFIRMED', 'Confirmed'),
        ('RESCHEDULED', 'Rescheduled'),
        ('CANCELLED', 'Cancelled'),
    ]
    application = models.OneToOneField('JobApplication', on_delete=models.CASCADE, related_name='scheduled_interview', db_index=True)
    availability_slot = models.OneToOneField(HRRecruiterAvailability, on_delete=models.PROTECT, related_name='booked_interview', db_index=True)
    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CONFIRMED', db_index=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Interview for App #{self.application_id} on {self.availability_slot.start_time}"


class AIReminderLog(models.Model):
    STAGE_CHOICES = [
        ('24_HOUR', '24 Hours Before Alert'),
        ('1_HOUR', '1 Hour Final Alert'),
    ]
    STATUS_CHOICES = [
        ('SUCCESS', 'Delivered successfully'),
        ('FAILED', 'Transmission Failure'),
    ]
    
    interview_schedule = models.ForeignKey('AIInterviewSchedule', on_delete=models.CASCADE, related_name='reminder_logs', db_index=True)
    reminder_stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    dispatched_at = models.DateTimeField(auto_now_add=True, db_index=True)
    error_details = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('interview_schedule', 'reminder_stage')

    def __str__(self):
        return f"Schedule #{self.interview_schedule_id} - Stage: {self.reminder_stage} ({self.status})"        


class AICandidateEvaluationReport(models.Model):
    application = models.OneToOneField('JobApplication', on_delete=models.CASCADE, related_name='evaluation_report', db_index=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        limit_choices_to={'role': 'EMPLOYER'},
        db_index=True
    )
    
    ats_match_score = models.FloatField(default=0.0)
    voice_screening_score = models.FloatField(default=0.0)
    
    executive_summary = models.TextField()
    identified_strengths = models.JSONField(default=list)
    identified_risks = models.JSONField(default=list)
    
    generated_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"AI Report: App #{self.application_id} - ATS: {self.ats_match_score}%"        


class SystemAuditTrailLog(models.Model):
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

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs_triggered', db_index=True)
    severity = models.CharField(max_length=10, choices=LOG_SEVERITY_CHOICES, default='INFO', db_index=True)
    category = models.CharField(max_length=15, choices=ACTION_CATEGORY_CHOICES, default='USER_ACTION', db_index=True)
    action_signature = models.CharField(max_length=255, db_index=True)
    detailed_payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "System Audit Trail Log"
        verbose_name_plural = "System Audit Trail Logs"
        indexes = [
            models.Index(fields=['severity', '-timestamp'], name='idx_audit_sev_time'),
            models.Index(fields=['category', '-timestamp'], name='idx_audit_cat_time'),
        ]

    def __str__(self):
        return f"[{self.severity}][{self.category}] {self.action_signature} at {self.timestamp}"        


# ==========================================
# 9. MONETIZATION & SAAS BILLING MODULES
# ==========================================
class SubscriptionPlan(models.Model):
    TIER_CHOICES = [
        ('FREE', 'Free Tier'),
        ('PRO', 'Pro Professional Tier'),
        ('ENTERPRISE', 'Enterprise Suite'),
    ]
    name = models.CharField(max_length=50, choices=TIER_CHOICES, unique=True, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    billing_cycle_days = models.IntegerField(default=30)
    max_job_postings = models.IntegerField(default=3)
    has_ai_analytics = models.BooleanField(default=False)
    has_voice_screening = models.BooleanField(default=False)
    has_premium_insights = models.BooleanField(default=False)  
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_name_display()} (${self.price})"


class UserSubscription(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active Subscription'),
        ('PAST_DUE', 'Payment Overdue Gracetrack'),
        ('CANCELLED', 'Cancelled Plan Account'),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription', db_index=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscribers', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE', db_index=True)
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(db_index=True)
    auto_renew = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', 'current_period_end'], name='idx_sub_status_end'),
        ]

    def is_valid(self):
        return self.status == 'ACTIVE' and self.current_period_end > timezone.now()

    def __str__(self):
        return f"{self.user.email} - {self.plan.name} ({self.status})"


class PaymentTransaction(models.Model):
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments', db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    gateway = models.CharField(max_length=15, choices=GATEWAY_CHOICES, default='STRIPE')
    gateway_reference_id = models.CharField(max_length=255, unique=True, blank=True, null=True, db_index=True)
    status = models.CharField(max_length=15, choices=TXN_STATUS, default='PENDING', db_index=True)
    processed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-processed_at'], name='idx_pay_user_date'),
        ]

    def __str__(self):
        return f"TXN-{self.id} - {self.user.email} (${self.amount}) - {self.status}"


class BillingHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='invoices', db_index=True)
    transaction = models.OneToOneField(PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    issued_date = models.DateTimeField(default=timezone.now, db_index=True)
    pdf_statement_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return f"INV-{self.invoice_number} for {self.user.email}"


class Transaction(models.Model):
    STATUS_CHOICES = [
        ('SUCCESS', 'Payment Completed'),
        ('FAILED', 'Payment Failed'),
        ('REFUNDED', 'Fully Refunded'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='transactions', db_index=True)
    subscription = models.ForeignKey(UserSubscription, on_delete=models.SET_NULL, null=True, blank=True, db_index=True)
    stripe_charge_id = models.CharField(max_length=255, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at'], name='idx_txn_status_date'),
        ]

    def __str__(self):
        return f"Txn {self.stripe_charge_id} - {self.amount} {self.currency}"


class RefundLog(models.Model):
    transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name='refund_details', db_index=True)
    reason = models.TextField()
    processed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='issued_refunds', db_index=True)
    refunded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Refund for Txn {self.transaction_id} at {self.refunded_at}"


class FinancialAuditLog(models.Model):
    SEVERITY_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Suspicious Activity'),
        ('CRITICAL', 'Payment Failure / Systemic Risk'),
    ]
    event_type = models.CharField(max_length=100, db_index=True)
    description = models.TextField()
    severity = models.CharField(max_length=15, choices=SEVERITY_CHOICES, default='INFO', db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['severity', '-timestamp'], name='idx_finaudit_sev_time'),
        ]

    def __str__(self):
        return f"[{self.severity}] {self.event_type} at {self.timestamp}"