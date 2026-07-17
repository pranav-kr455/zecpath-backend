import os 
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser, Employer, Candidate, JobPost, JobApplication



# ==========================================
# 1. NEW CUSTOM JWT TOKEN SERIALIZER
# ==========================================
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Force SimpleJWT to inject the uppercase role string into the JWT claims payload
        token['role'] = str(user.role).upper()
        return token


# ==========================================
# 2. USER REGISTRATION SERIALIZER
# ==========================================
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6, style={'input_type': 'password'})

    class Meta:
        model = CustomUser
        fields = ['email', 'phone', 'role', 'password']

    def validate_email(self, value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        return CustomUser.objects.create_user(**validated_data)
    

# ==========================================
# 3. EMPLOYER PROFILE SERIALIZER
# ==========================================
class EmployerProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Employer
        fields = ['id', 'email', 'company_name', 'domain', 'company_size', 'is_profile_verified']
        read_only_fields = ['id', 'is_profile_verified']


# ==========================================
# 4. CANDIDATE PROFILE SERIALIZER
# ==========================================
class CandidateProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    resume = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = Candidate
        fields = ['id', 'email', 'skills', 'education', 'experience', 'expected_salary', 'resume']
        read_only_fields = ['id']

    def validate_resume(self, value):
        if not value:
            return value

        # 1. Enforce Size Limitations (5MB max)
        max_size = 5 * 1024 * 1024  # 5 Megabytes
        if value.size > max_size:
            raise serializers.ValidationError("File size exceeds the maximum limit of 5MB.")

        # 2. Enforce File Extension Verification
        ext = os.path.splitext(value.name)[1].lower()
        valid_extensions = ['.pdf', '.doc', '.docx']
        if ext not in valid_extensions:
            raise serializers.ValidationError("Unsupported file extension. Please upload a PDF, DOC, or DOCX.")

        return value
    

# ==========================================
# 5. ENHANCED OPERATIONAL ATS SERIALIZER (DAY 16)
# ==========================================
class JobPostSerializer(serializers.ModelSerializer):
    """
    Day 16 Enhanced: Formats JobPost structural business matrices into clean
    outbound JSON vectors and handles corporate validation rules.
    """
    employer_name = serializers.CharField(source='employer_profile.company_name', read_only=True)

    class Meta:
        model = JobPost
        fields = [
            'id', 
            'employer_profile', 
            'employer_name',
            'title', 
            'description', 
            'skills_required',
            'experience_years',
            'location', 
            'job_type',
            'salary', 
            'status', 
            'created_at', 
            'updated_at'
        ]
        read_only_fields = ['id', 'employer_profile', 'created_at', 'updated_at']


# ==========================================
# 6. JOB APPLICATION SERIALIZER (DAY 18)
# ==========================================
class JobApplicationSerializer(serializers.ModelSerializer):
    """
    Day 18: Formats candidate job applications into structured data feeds.
    Automatically resolves relational titles and employer company names.
    """
    candidate_email = serializers.CharField(source='candidate_profile.user.email', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    company_name = serializers.CharField(source='job.employer_profile.company_name', read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 
            'job', 
            'job_title', 
            'company_name', 
            'candidate_profile', 
            'candidate_email', 
            'resume_snapshot', 
            'status', 
            'applied_at'
        ]
        # Most fields are read-only because views auto-inject profile attachments
        read_only_fields = ['id', 'candidate_profile', 'status', 'resume_snapshot', 'applied_at']

class ATSStatusUpdateSerializer(serializers.ModelSerializer):
    """
    Day 19: Special operational serializer built strictly for parsing 
    employer status mutations and handling transaction notes.
    """
    notes = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = JobApplication
        fields = ['status', 'notes']

    def validate_status(self, value):
        # Normalize incoming data matrix values
        valid_statuses = ['APPLIED', 'REVIEWING', 'INTERVIEW', 'OFFER', 'REJECTED']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"'{value}' is not a valid operational hiring tier.")
        return value        



