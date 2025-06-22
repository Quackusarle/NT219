from django.urls import path
from .views import CPABESetupView, PublicKeyView, GenerateSecretKeyView
from .views import CustomTokenObtainPairView
from django.conf import settings
from django.http import HttpResponse

app_name = 'cpabe_service_app'
urlpatterns = [
    path('setup/', CPABESetupView.as_view(), name='cpabe_setup'),
    path('public-key/', PublicKeyView.as_view(), name='cpabe_public_key'),
    path('generate-secret-key/', GenerateSecretKeyView.as_view(), name='cpabe_generate_secret_key'),
    path('token/', CustomTokenObtainPairView.as_view(), name='custom_token_obtain_pair'),
]