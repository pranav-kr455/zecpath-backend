from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import JobPost, Candidate  # Make sure EmployerProfile model imports safely if explicitly separated
from django.apps import apps
import io

class ZecPathSecurityAndWorkflowTestCase(APITestCase):
    """
    Day 29: Automated Unit & Integration Testing Suite auditing access controls,
    workflow validation boundaries, and cross-endpoint security leaks.
    """

    def setUp(self):
        User = get_user_model()
        
        # 1. Initialize Candidate Test Fixture User
        self.candidate_user = User.objects.create_user(
            email='candidate@zecpath.com',
            password='Password123!'
        )
        self.candidate_profile, _ = Candidate.objects.get_or_create(user=self.candidate_user)
        
        # 2. Initialize Employer Test Fixture User to fulfill relational constraints
        self.employer_user = User.objects.create_user(
            email='employer@zecpath.com',
            password='Password123!'
        )
        
        # Safely fetch the employer profile model layout dynamically based on your app components
        EmployerModel = apps.get_model('core', 'Employer') # Adjust string to 'EmployerProfile' if that is your model's class name
        self.employer_profile, _ = EmployerModel.objects.get_or_create(user=self.employer_user)
        
        # 3. Initialize a Job Post Fixture containing the mandatory Employer relation field!
        self.job = JobPost.objects.create(
            employer_profile=self.employer_profile,  # ✨ Injects missing relationship lock!
            title='Junior Python Full-Stack Developer',
            description='Django backend logic optimization test post.',
            skills_required='Python, Django, React',
            experience_years=1
        )
        
        # 4. Target API Endpoint URLs
        self.apply_url = reverse('job_apply_automated_workflow', kwargs={'job_id': self.job.id})
        self.dashboard_url = reverse('hr_dashboard_optimized')

    def test_apply_endpoint_requires_authentication(self):
        """🛡️ SECURITY AUDIT TASK: Verify unauthenticated requests are blocked instantly."""
        response = self.client.post(self.apply_url, data={})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_hr_dashboard_blocks_unauthorized_access(self):
        """🛡️ SECURITY AUDIT TASK: Ensure regular candidates cannot read the secure recruiter dashboard data."""
        # Authenticate as a standard candidate user
        self.client.force_authenticate(user=self.candidate_user)
        
        # Hit the optimized HR dashboard route
        response = self.client.get(self.dashboard_url)
        
        # Verify access is restricted for normal applicants
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])

    def test_invalid_file_format_handling(self):
        """🐛 BUG RESOLUTION / REGRESSION TASK: Ensure code safely handles invalid extensions without crashing."""
        self.client.force_authenticate(user=self.candidate_user)
        
        # Mock a corrupt text file instead of a valid PDF document stream
        mock_text_file = io.BytesIO(b"Fake resume contents string.")
        mock_text_file.name = "resume.txt" # Invalid format extension
        
        response = self.client.post(self.apply_url, {'resume': mock_text_file}, format='multipart')
        
        # Verify the backend handles it gracefully with a 415 error instead of an internal 500 server crash
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)