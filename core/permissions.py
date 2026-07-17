from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import Roles

# ==========================================
# 1. GLOBAL ROLE-BASED ACCESS CONTROL (RBAC)
# ==========================================

class IsAdminUser(BasePermission):
    """Allows access only to users explicitly marked with the ADMIN role."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(request.user.role).upper() == str(Roles.ADMIN).upper()
        )


class IsEmployerUser(BasePermission):
    """Allows access only to users explicitly marked with the EMPLOYER role."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(request.user.role).upper() == str(Roles.EMPLOYER).upper()
        )


class IsCandidateUser(BasePermission):
    """Allows access only to users explicitly marked with the CANDIDATE role."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(request.user.role).upper() == str(Roles.CANDIDATE).upper()
        )


# ==========================================
# 2. OBJECT-LEVEL OWNERSHIP ENFORCEMENT (DAY 16)
# ==========================================

class IsEmployerOwner(BasePermission):
    """
    Day 16: Restricts operational modifications strictly to the specific 
    authenticated Employer account who originally created the record.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(request.user.role).upper() == str(Roles.EMPLOYER).upper()
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.employer_profile.user == request.user