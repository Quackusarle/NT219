import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from allauth.account.signals import user_logged_in
from django.dispatch import receiver
from .models import User, UserAttribute, ProtectedData
from .abe_utils import generate_user_secret_key, get_public_parameters_for_client

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['user_attributes'] = UserAttribute.objects.filter(user=self.request.user)
            context['user_data_count'] = ProtectedData.objects.filter(owner_user=self.request.user).count()
        return context

@login_required
def dashboard_view(request):
    """Dashboard cho user đã đăng nhập"""
    user_attributes = UserAttribute.objects.filter(user=request.user)
    user_data = ProtectedData.objects.filter(owner_user=request.user)
    
    context = {
        'user_attributes': user_attributes,
        'user_data': user_data,
        'total_attributes': user_attributes.count(),
        'total_data_items': user_data.count(),
    }
    
    return render(request, 'dashboard.html', context)

@login_required
@require_http_methods(["GET"])
def get_user_secret_key(request):
    """
    API endpoint để lấy CP-ABE secret key của user hiện tại.
    """
    try:
        # Generate secret key cho user
        key_data = generate_user_secret_key(request.user)
        
        return JsonResponse({
            'success': True,
            'data': key_data,
            'message': 'Secret key generated successfully'
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'User has no attributes assigned'
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Error generating secret key'
        }, status=500)

@require_http_methods(["GET"])
def get_public_parameters(request):
    """
    API endpoint để lấy CP-ABE public parameters.
    Endpoint này có thể public vì PK không cần bảo mật.
    """
    try:
        pk_data = get_public_parameters_for_client()
        
        return JsonResponse({
            'success': True,
            'public_key': pk_data,
            'message': 'Public parameters retrieved successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Error retrieving public parameters'
        }, status=500)

@login_required
def profile_view(request):
    """Profile page cho user"""
    if request.method == 'POST':
        # Update profile logic
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'profile.html')

@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'authenticated': request.user.is_authenticated,
        'user': request.user.email if request.user.is_authenticated else None
    })

# Signal handler để tự động load key khi user đăng nhập
@receiver(user_logged_in)
def handle_user_login(sender, request, user, **kwargs):
    """
    Khi user đăng nhập thành công, tự động generate secret key
    và store vào session để client có thể lấy.
    """
    try:
        # Generate secret key cho user
        key_data = generate_user_secret_key(user)
        
        # Store key data vào session
        request.session['abe_secret_key'] = key_data
        request.session['abe_key_generated_at'] = str(user.last_login)
        
        print(f"ABE secret key generated and stored in session for user: {user.email}")
        
    except Exception as e:
        print(f"Error generating ABE secret key for user {user.email}: {e}")
        # Không raise exception để không ảnh hưởng đến login process

@login_required
@require_http_methods(["GET"])
def get_session_secret_key(request):
    """
    Lấy secret key từ session (đã được generate khi login).
    """
    key_data = request.session.get('abe_secret_key')
    
    if key_data:
        return JsonResponse({
            'success': True,
            'data': key_data,
            'message': 'Secret key retrieved from session'
        })
    else:
        # Nếu không có trong session, generate mới
        try:
            key_data = generate_user_secret_key(request.user)
            request.session['abe_secret_key'] = key_data            
            return JsonResponse({
                'success': True,
                'data': key_data,
                'message': 'Secret key generated and stored in session'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e),
                'message': 'Error generating secret key'
            }, status=500)