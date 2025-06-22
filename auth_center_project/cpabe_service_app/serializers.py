from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from cpabe_service_app.models import UserProfile
from dj_rest_auth.serializers import LoginSerializer
import logging

logger = logging.getLogger(__name__)

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        logger.info(f"MyTokenObtainPairSerializer.get_token called for user: {user.username}")
        token = super().get_token(user) # Lấy token gốc từ simplejwt

        # Thêm các claim tùy chỉnh vào payload của Access Token
        try:
            profile = UserProfile.objects.get(user=user)
            # Sử dụng method có sẵn để lấy attributes
            user_attributes = profile.get_attributes_string()
            
            logger.info(f"User {user.username} attributes: {user_attributes}")
            
            # Thêm attributes vào token
            token['user_attributes'] = user_attributes
            
            # Có thể thêm thêm thông tin khác
            token['username'] = user.username
            token['email'] = user.email
            
            logger.info(f"Token claims added for user {user.username}")

        except UserProfile.DoesNotExist:
            # Xử lý trường hợp user không có profile
            logger.warning(f"UserProfile not found for user: {user.username}")
            token['user_attributes'] = ""
            token['username'] = user.username
            token['email'] = user.email

        return token

class CustomLoginSerializer(LoginSerializer):
    """
    Custom login serializer để đảm bảo dj-rest-auth sử dụng custom JWT serializer
    """
    def get_auth_user_using_allauth(self, username, email, password):
        # Gọi method gốc để authenticate user
        return super().get_auth_user_using_allauth(username, email, password)