from django.contrib import admin
from .models import CustomUser, Employer, Candidate, JobPost, JobApplication

class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'is_active', 'is_verified', 'created_at')
    list_filter = ('role', 'is_active', 'is_verified')
    search_fields = ('email',)
    ordering = ('-created_at',)

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Employer)
admin.site.register(Candidate)
admin.site.register(JobPost)  # ⚡ Updated from Job to JobPost
admin.site.register(JobApplication)