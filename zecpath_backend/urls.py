from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Clean, standard administration route mapping
    path('admin/', admin.site.urls),
    
    # Forwarding all application requests to your core endpoints
    path('api/', include('core.urls')),
]