from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import UserAttribute

def requires_attributes(redirect_url='home'):
    """
    Decorator yêu cầu user phải có ít nhất 1 attribute để truy cập.
    Nếu không có attribute, redirect về trang home.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Kiểm tra user có attribute nào không
            has_attributes = UserAttribute.objects.filter(user=request.user).exists()
            
            if not has_attributes:
                messages.warning(
                    request, 
                    'Bạn chưa được gán thuộc tính truy cập. Vui lòng liên hệ quản trị viên.'
                )
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def api_requires_attributes():
    """
    Decorator cho API endpoints - trả về JSON error thay vì redirect
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Kiểm tra user có attribute nào không
            has_attributes = UserAttribute.objects.filter(user=request.user).exists()
            
            if not has_attributes:
                return JsonResponse({
                    'success': False,
                    'error': 'ACCESS_DENIED',
                    'message': 'Bạn chưa được gán thuộc tính truy cập. Vui lòng liên hệ quản trị viên.'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def requires_doctor_role(redirect_url='home'):
    """
    Decorator yêu cầu user phải có attribute 'doctor' để truy cập.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Kiểm tra user có attribute doctor không
            is_doctor = UserAttribute.objects.filter(
                user=request.user,
                attribute__name__in=['doctor']
            ).exists()
            
            if not is_doctor:
                messages.error(
                    request, 
                    'Chỉ có bác sĩ mới có quyền truy cập chức năng này.'
                )
                return redirect(redirect_url)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def api_requires_doctor_role():
    """
    Decorator cho API endpoints - chỉ cho phép bác sĩ truy cập
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # Kiểm tra user có attribute doctor không
            is_doctor = UserAttribute.objects.filter(
                user=request.user,
                attribute__name__in=['doctor']
            ).exists()
            
            if not is_doctor:
                return JsonResponse({
                    'success': False,
                    'error': 'DOCTOR_ONLY',
                    'message': 'Chỉ có bác sĩ mới có quyền sử dụng chức năng này.'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator 