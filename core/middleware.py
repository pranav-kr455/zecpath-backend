from django.utils import timezone
from django.http import JsonResponse
from core.models import UserSubscription

class SubscriptionEnforcementMiddleware:
    """
    Day 48: Global Middleware to inspect user subscription statuses,
    enforce grace track parameters, and handle automatic deactivation windows.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only process authenticated requests targeting billing-guarded modules
        if request.user.is_authenticated and not request.path.startswith('/admin/'):
            try:
                subscription = UserSubscription.objects.get(user=request.user)
                
                # Check if the subscription period has expired
                if subscription.current_period_end < timezone.now():
                    # Calculate grace track allowance window (e.g., 3 days buffer)
                    grace_end_period = subscription.current_period_end + timezone.timedelta(days=3)
                    
                    if timezone.now() <= grace_end_period:
                        # Soft warning state: Demote to past due, but allow execution thread
                        if subscription.status != 'PAST_DUE':
                            subscription.status = 'PAST_DUE'
                            subscription.save()
                    else:
                        # Automatic Deactivation: Hard cut-off exceeded
                        if subscription.status != 'CANCELLED':
                            subscription.status = 'CANCELLED'
                            subscription.save()
            except UserSubscription.DoesNotExist:
                # If no subscription tracking record exists, pass along (assumed Free Tier defaults)
                pass

        response = self.get_response(request)
        return response