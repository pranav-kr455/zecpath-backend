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
            str(getattr(request.user, 'role', '')).upper() == str(Roles.ADMIN).upper()
        )


class IsEmployerUser(BasePermission):
    """Allows access only to users explicitly marked with the EMPLOYER role."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(getattr(request.user, 'role', '')).upper() == str(Roles.EMPLOYER).upper()
        )


class IsCandidateUser(BasePermission):
    """Allows access only to users explicitly marked with the CANDIDATE role."""
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(getattr(request.user, 'role', '')).upper() == str(Roles.CANDIDATE).upper()
        )


class IsEmployerOrReadOnly(BasePermission):
    """
    Day 55 Hardening: Read-only access for safe HTTP methods (GET, HEAD, OPTIONS).
    Write operations require an authenticated user with the EMPLOYER role.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(getattr(request.user, 'role', '')).upper() == str(Roles.EMPLOYER).upper()
        )


# ==========================================
# 2. OBJECT-LEVEL OWNERSHIP ENFORCEMENT
# ==========================================

class IsEmployerOwner(BasePermission):
    """
    Restricts operational modifications strictly to the specific 
    authenticated Employer account who originally created the record.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(getattr(request.user, 'role', '')).upper() == str(Roles.EMPLOYER).upper()
        )

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        # Checks if object directly links to employer profile or user
        owner_profile = getattr(obj, 'employer_profile', None)
        if owner_profile and hasattr(owner_profile, 'user'):
            return owner_profile.user == request.user
        
        owner_user = getattr(obj, 'user', None)
        return owner_user == request.user


class IsCandidateOwner(BasePermission):
    """
    Day 55 Hardening (BOLA Prevention): Ensures candidates can strictly access 
    and modify only their own candidate profiles, applications, and documents.
    """
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            str(getattr(request.user, 'role', '')).upper() == str(Roles.CANDIDATE).upper()
        )

    def has_object_permission(self, request, view, obj):
        # Admins override ownership checks
        if str(getattr(request.user, 'role', '')).upper() == str(Roles.ADMIN).upper():
            return True

        # Resolves ownership across Candidate Profile, JobApplication, or Direct User link
        candidate_rel = getattr(obj, 'candidate', getattr(obj, 'candidate_profile', None))
        if candidate_rel and hasattr(candidate_rel, 'user'):
            return candidate_rel.user == request.user

        owner_user = getattr(obj, 'user', None)
        return owner_user == request.user