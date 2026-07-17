from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Employer, Candidate, Roles

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Convert values explicitly to uppercase strings to prevent Enum mismatches
        user_role = str(instance.role).upper()
        
        if user_role == str(Roles.EMPLOYER).upper():
            Employer.objects.get_or_create(user=instance)
        elif user_role == str(Roles.CANDIDATE).upper():
            Candidate.objects.get_or_create(user=instance)