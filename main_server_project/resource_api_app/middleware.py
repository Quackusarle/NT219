from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from .authentication import CustomJWTAuthentication
import logging

logger = logging.getLogger(__name__)

class JWTAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware để áp dụng JWT authentication cho function-based views
    """
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.jwt_authenticator = CustomJWTAuthentication()
    
    def process_request(self, request):
        """
        Thêm JWT authentication vào request cho function-based views
        """
        # Bỏ qua nếu đã có user được authenticate
        if hasattr(request, 'user') and request.user.is_authenticated:
            return None
        
        # Bỏ qua cho API endpoints (đã có authentication trong APIView)
        if request.path.startswith('/api/'):
            return None
        
        # Bỏ qua cho static files và admin
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return None
            
        try:
            # Thử authenticate với JWT token
            auth_result = self.jwt_authenticator.authenticate(request)
            
            if auth_result is not None:
                user, token = auth_result
                request.user = user
                request.auth = token
                logger.debug(f"JWT middleware authenticated user: {user.id}")
            else:
                # Không có token hoặc token không hợp lệ
                request.user = AnonymousUser()
                request.auth = None
                
        except Exception as e:
            logger.debug(f"JWT middleware authentication failed: {e}")
            request.user = AnonymousUser()
            request.auth = None
        
        return None 