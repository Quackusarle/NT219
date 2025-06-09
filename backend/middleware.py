from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from .models import UserAttribute

class AttributeAccessMiddleware:
    """
    Middleware để kiểm soát truy cập server-side dựa trên attributes của user.
    Chặn truy cập tất cả URLs ngoại trừ home và auth nếu user chưa có attributes.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URLs được phép truy cập mà không cần attributes
        self.allowed_urls = [
            '/',  # home
            '/accounts/',  # allauth URLs
            '/health/',  # health check
        ]
        
        # URLs được phép với prefix
        self.allowed_prefixes = [
            '/accounts/',  # tất cả auth URLs
            '/admin/',     # admin interface
            '/static/',    # static files
            '/media/',     # media files
        ]

    def __call__(self, request):
        # Chỉ áp dụng cho user đã đăng nhập
        if request.user.is_authenticated:
            # Kiểm tra user có attributes hay không
            has_attributes = UserAttribute.objects.filter(user=request.user).exists()
            
            if not has_attributes:
                request_path = request.path
                
                # Kiểm tra nếu URL được phép
                is_allowed = (
                    request_path in self.allowed_urls or
                    any(request_path.startswith(prefix) for prefix in self.allowed_prefixes)
                )
                
                if not is_allowed:
                    # Kiểm tra nếu là API request
                    if request.path.startswith('/api/') or request.headers.get('Content-Type') == 'application/json':
                        return JsonResponse({
                            'success': False,
                            'error': 'ACCESS_DENIED',
                            'message': 'Bạn chưa được gán thuộc tính truy cập. Vui lòng liên hệ quản trị viên.',
                            'redirect_url': reverse('home')
                        }, status=403)
                    else:
                        # Web request - redirect về home với message
                        messages.warning(
                            request, 
                            'Bạn chưa được gán thuộc tính truy cập. Vui lòng liên hệ quản trị viên để được cấp quyền.'
                        )
                        return redirect('home')
        
        response = self.get_response(request)
        return response