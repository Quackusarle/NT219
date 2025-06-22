"""
URL configuration for auth_center_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
# auth_center_project/urls.py

from django.contrib import admin
from django.urls import path, include   
from cpabe_service_app.views import CustomTokenObtainPairView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/cpabe/', include('cpabe_service_app.urls')),
    
    # Custom JWT login endpoint with attributes
    path('api/auth/login/', CustomTokenObtainPairView.as_view(), name='custom_login'),
    
    # Other dj-rest-auth endpoints (excluding login)
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
]