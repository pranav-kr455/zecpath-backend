from functools import wraps
from rest_framework.response import Response
from rest_framework import status
from core.models import UserSubscription, SubscriptionPlan

def require_premium_feature(feature_name):
    """
    Day 48: Core view decorator to guard specific computational pathways
    Options: 'has_ai_analytics', 'has_voice_screening'
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                subscription = UserSubscription.objects.get(user=request.user)
                
                # Enforce active standing constraint
                if subscription.status not in ['ACTIVE', 'PAST_DUE']:
                    return Response({
                        "error": "SUBSCRIPTION_REQUIRED",
                        "message": "Access restricted. An active subscription plan is required."
                    }, status=status.HTTP_402_PAYMENT_REQUIRED)
                
                # Inspect structural catalog permission parameters
                plan_permissions = subscription.plan
                feature_allowed = getattr(plan_permissions, feature_name, False)
                
                if not feature_allowed:
                    return Response({
                        "error": "TIER_INSUFFICIENT",
                        "message": f"Upgrade your plan tier to unlock the '{feature_name}' feature set."
                    }, status=status.HTTP_403_FORBIDDEN)
                    
            except UserSubscription.DoesNotExist:
                return Response({
                    "error": "BILLING_RECORD_MISSING",
                    "message": "Free tier default accounts lack premium feature access permission tokens."
                }, status=status.HTTP_402_PAYMENT_REQUIRED)
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator