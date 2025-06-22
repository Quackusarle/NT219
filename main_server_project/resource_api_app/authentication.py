from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import AnonymousUser
import logging

logger = logging.getLogger(__name__)

class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication class cho Resource Server
    Xác thực JWT tokens từ Auth Center sử dụng EC public key
    và parse các custom claims như user_attributes
    """
    
    def get_user(self, validated_token):
        """
        Tạo user object từ validated token với custom claims từ Auth Center
        """
        try:
            # Lấy user_id từ token (theo cấu hình USER_ID_CLAIM)
            user_id = validated_token.get('user_id')
            if user_id is None:
                logger.error("No user_id found in token from Auth Center")
                raise InvalidToken('Token contained no recognizable user identification')
            
            # Tạo user object với thông tin từ Auth Center token
            class AuthenticatedUser:
                def __init__(self, user_id):
                    self.id = user_id
                    self.is_authenticated = True
                    self.is_anonymous = False
                    self.is_active = True
            
            user = AuthenticatedUser(user_id)
            
            # Parse các thông tin cơ bản
            user.username = validated_token.get('username', f'user_{user_id}')
            user.email = validated_token.get('email', '')
            
            # Parse custom attributes từ Auth Center (quan trọng cho ABAC)
            user.user_attributes = validated_token.get('user_attributes', '')
            
            # Log thông tin user đã được authenticate
            logger.info(f"Successfully authenticated user from Auth Center: id={user.id}, username={user.username}")
            logger.debug(f"User attributes: {user.user_attributes}")
            
            return user
            
        except Exception as e:
            logger.error(f"Error parsing token from Auth Center: {e}")
            raise InvalidToken('Invalid token from Auth Center') 