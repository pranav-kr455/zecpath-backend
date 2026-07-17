from django_filters import rest_framework as filters
from .models import JobPost

class JobPostFilter(filters.FilterSet):
    """
    Day 17: Advanced Filter Matrix handling range queries,
    case-insensitive locations, and specific job categories.
    """
    # Min/Max range selectors for Experience
    min_experience = filters.NumberFilter(field_name="experience_years", lookup_expr='gte')
    max_experience = filters.NumberFilter(field_name="experience_years", lookup_expr='lte')
    
    # Min/Max range selectors for Salary
    min_salary = filters.NumberFilter(field_name="salary", lookup_expr='gte')
    max_salary = filters.NumberFilter(field_name="salary", lookup_expr='lte')
    
    # Case-insensitive fuzzy matching for location and skills
    location = filters.CharFilter(field_name="location", lookup_expr='icontains')
    skills = filters.CharFilter(field_name="skills_required", lookup_expr='icontains')

    class Meta:
        model = JobPost
        fields = ['job_type', 'status', 'location', 'skills']