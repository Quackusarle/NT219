from django.urls import path
from .views import *
from . import views

app_name = 'resource_api_app' # Hoặc tên app của bạn

urlpatterns = [
    path('accounts/login/', views.login_page_on_main_server_view, name='rs_login_page'),
    path('home/', views.home_view, name='rs_home_page'),
    path('upload/', views.upload_document_page_view, name='rs_upload_page'),
    path('decrypt/', views.decrypt_document_page_view, name='rs_decrypt_page'),
    path('decrypt-record/<uuid:record_id>/', views.decrypt_record_page_view, name='rs_decrypt_record_page'),
    
    path('api/auth/test/', views.TestAuthView.as_view(), name='api_test_auth'),
    path('api/ehr/upload/', views.UploadEHRTextView.as_view(), name='api_upload_ehr'),
    path('api/ehr/patient/<str:patient_id>/', views.ListEHRByPatientView.as_view(), name='api_list_ehr_by_patient'),
    path('api/ehr/<uuid:entry_id_uuid>/', views.RetrieveEHRTextView.as_view(), name='api_retrieve_ehr'),
]