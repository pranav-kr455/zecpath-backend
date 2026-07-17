import os
import django

# Setup Django environment variables
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zecpath_backend.settings')
django.setup()

from core.models import Employer, JobPost

def seed_database():
    emp = Employer.objects.first()
    if not emp:
        print("❌ ERROR: No Employer profile found! Create an employer via your signup API first.")
        return
    
    # 12 diverse variations matching your exact view and serializer requirements
    data = [
        {'t': 'Junior Python Developer', 'c': 'ZecPath Solutions', 'l': 'Palakkad', 's': 45000.00, 'st': 'ACTIVE', 'd': 'Django backend development focus.'},
        {'t': 'React Frontend Engineer', 'c': 'Lumina Tech', 'l': 'Remote', 's': 55000.00, 'st': 'ACTIVE', 'd': 'Building responsive layouts with UI hooks.'},
        {'t': 'Full-Stack Python Developer', 'c': 'ZecPath Solutions', 'l': 'Palakkad', 's': 65000.00, 'st': 'ACTIVE', 'd': 'Django REST Framework and React ecosystem integration.'},
        {'t': 'DevOps Intern', 'c': 'CloudScale Inc', 'l': 'Kochi', 's': 25000.00, 'st': 'ACTIVE', 'd': 'Automating CI/CD deployment pipelines.'},
        {'t': 'Database Administrator', 'c': 'DataGate Corp', 'l': 'Bangalore', 's': 70000.00, 'st': 'PAUSED', 'd': 'Optimizing PostgreSQL indexing schemas.'},
        {'t': 'Django Backend Intern', 'c': 'ZecPath Solutions', 'l': 'Palakkad', 's': 20000.00, 'st': 'ACTIVE', 'd': 'Writing high performance serializers and validation matrix code.'},
        {'t': 'Senior React Architect', 'c': 'Lumina Tech', 'l': 'Remote', 's': 95000.00, 'st': 'ACTIVE', 'd': 'Designing dynamic custom context providers.'},
        {'t': 'QA Automation Engineer', 'c': 'ZecPath Solutions', 'l': 'Palakkad', 's': 40000.00, 'st': 'CLOSED', 'd': 'Building test tracking validation suites.'},
        {'t': 'Python Data Analyst', 'c': 'Alpha Analytics', 'l': 'Coimbatore', 's': 48000.00, 'st': 'ACTIVE', 'd': 'Evaluating pipeline flows using Pandas.'},
        {'t': 'UI/UX Designer', 'c': 'PixelCraft Studio', 'l': 'Remote', 's': 38000.00, 'st': 'ACTIVE', 'd': 'Prototyping advanced application tracking user vectors.'},
        {'t': 'Technical Writer', 'c': 'ZecPath Solutions', 'l': 'Palakkad', 's': 30000.00, 'st': 'ACTIVE', 'd': 'Documenting production-ready REST API frameworks.'},
        {'t': 'Lead Software Engineer', 'c': 'Nexus Systems', 'l': 'Ernakulam', 's': 120000.00, 'st': 'ACTIVE', 'd': 'Architecting distributed corporate system design layers.'}
    ]
    
    # Map objects and bulk create to avoid N+1 slow loops during seeding
    job_instances = [
        JobPost(
            employer_profile=emp,
            title=item['t'],
            company_name=item['c'],
            location=item['l'],
            salary=item['s'],
            status=item['st'],
            description=item['d']
        ) for item in data
    ]
    
    JobPost.objects.bulk_create(job_instances)
    print("🚀 SUCCESS: 12 production-scalable job records pooled into the database!")

if __name__ == '_main_':
    seed_database()