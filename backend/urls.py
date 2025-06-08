from django.urls import path
from . import views


urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('profile/', views.profile_view, name='profile'),
    path('health/', views.health_check, name='health_check'),
    
    # Medical Record Upload
    path('medical-upload/', views.medical_upload_view, name='medical_upload'),
    
    # CP-ABE Waters11 API endpoints
    path('api/abe/secret-key/', views.get_user_secret_key, name='get_user_secret_key'),
    path('api/abe/public-key/', views.get_public_parameters, name='get_public_parameters'),
    path('api/abe/session-key/', views.get_session_secret_key, name='get_session_secret_key'),
    
    # Medical Record API endpoints
    path('api/access-policies/', views.get_access_policies, name='get_access_policies'),
    path('api/upload-medical-record/', views.upload_medical_record, name='upload_medical_record'),
]