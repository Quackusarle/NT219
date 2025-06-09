import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from allauth.account.signals import user_logged_in
from django.dispatch import receiver
from .models import User, UserAttribute, MedicalData, AccessPolicy
from .abe_utils import generate_user_secret_key, get_public_parameters_for_client, create_medical_data_record

class HomeView(TemplateView):
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            context['user_attributes'] = UserAttribute.objects.filter(user=self.request.user)
            context['user_data_count'] = MedicalData.objects.filter(owner_user=self.request.user).count()
        return context

@login_required
def dashboard_view(request):
    """Dashboard cho user đã đăng nhập - hiển thị toàn bộ dữ liệu"""
    user_attributes = UserAttribute.objects.filter(user=request.user)
    # Query toàn bộ dữ liệu thay vì chỉ dữ liệu của user hiện tại
    all_data = MedicalData.objects.all().order_by('-created_at')
    
    context = {
        'user_attributes': user_attributes,
        'all_data': all_data,  # Đổi tên từ user_data thành all_data
        'total_attributes': user_attributes.count(),
        'total_data_items': all_data.count(),
    }
    
    return render(request, 'dashboard.html', context)

@login_required
@require_http_methods(["GET"])
def get_user_secret_key(request):
    """
    API endpoint để lấy CP-ABE Waters11 secret key của user hiện tại.
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

@ensure_csrf_cookie
@require_http_methods(["GET"])
def get_public_parameters(request):
    """
    API endpoint để lấy CP-ABE Waters11 public parameters.
    Endpoint này có thể public vì PK không cần bảo mật.
    """
    try:
        pk_data = get_public_parameters_for_client()
        
        return JsonResponse({
            'success': True,
            'data': pk_data,
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
        'user': request.user.email if request.user.is_authenticated else None,
        'scheme': 'waters11'
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
        request.session['abe_key_generated_at'] = str(user.last_login or 'now')
        
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
    try:
        key_data = request.session.get('abe_secret_key')
        
        if key_data:
            return JsonResponse({
                'success': True,
                'data': key_data,
                'message': 'Secret key retrieved from session',
                'source': 'session'
            })
        else:
            # Nếu không có trong session, generate mới
            key_data = generate_user_secret_key(request.user)
            request.session['abe_secret_key'] = key_data
            
            return JsonResponse({
                'success': True,
                'data': key_data,
                'message': 'Secret key generated and stored in session',
                'source': 'generated'
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

# THÊM MỚI: View và API endpoints cho medical record upload

@login_required
def medical_upload_view(request):
    """Trang upload medical record"""
    return render(request, 'medical_upload.html')

@login_required
@require_http_methods(["GET"])
def get_access_policies(request):
    """
    API endpoint để lấy danh sách access policies
    """
    try:
        policies = AccessPolicy.objects.all().order_by('name')
        policy_list = []
        
        for policy in policies:
            policy_list.append({
                'id': policy.id,
                'name': policy.name,
                'policy_template': policy.policy_template,
                'description': policy.description
            })
        
        return JsonResponse({
            'success': True,
            'data': policy_list,
            'count': len(policy_list),
            'message': 'Access policies retrieved successfully'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Error retrieving access policies'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def upload_medical_record(request):
    """
    API endpoint để upload medical record đã mã hóa
    """
    try:
        # Parse JSON data từ request
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = [
            'patient_id',
            'patient_info_aes_key_blob',
            'patient_info_aes_iv_blob',
            'medical_record_aes_key_blob', 
            'medical_record_aes_iv_blob'
        ]
        
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required field: {field}',
                    'message': 'Thiếu thông tin bắt buộc'
                }, status=400)
        
        # Convert base64 strings to bytes
        encrypted_data = {}
        binary_fields = [
            'patient_info_aes_key_blob', 'patient_info_aes_iv_blob',
            'medical_record_aes_key_blob', 'medical_record_aes_iv_blob',
            'patient_name_blob', 'patient_age_blob',
            'patient_gender_blob', 'patient_phone_blob',
            'chief_complaint_blob', 'past_medical_history_blob',
            'diagnosis_blob', 'status_blob'
        ]
        
        import base64
        for field in binary_fields:
            if field in data and data[field]:
                try:
                    encrypted_data[field] = base64.b64decode(data[field])
                except Exception as e:
                    return JsonResponse({
                        'success': False,
                        'error': f'Invalid base64 data for field: {field}',
                        'message': f'Dữ liệu mã hóa không hợp lệ: {field}'
                    }, status=400)
        
        # Create medical record
        medical_record = create_medical_data_record(
            owner_user=request.user,
            patient_id=data['patient_id'],
            **encrypted_data
        )
        
        if medical_record:
            return JsonResponse({
                'success': True,
                'data': {
                    'id': medical_record.id,
                    'patient_id': medical_record.patient_id,
                    'created_at': medical_record.created_at.isoformat()
                },
                'message': 'Medical record uploaded successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to create medical record',
                'message': 'Không thể tạo hồ sơ y tế'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data',
            'message': 'Dữ liệu JSON không hợp lệ'
        }, status=400)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'message': 'Lỗi khi upload medical record'
        }, status=500)

@login_required
def medical_record_detail_view(request, record_id):
    """View để hiển thị chi tiết một medical record"""
    try:
        medical_record = MedicalData.objects.get(id=record_id)
        user_attributes = UserAttribute.objects.filter(user=request.user)
        
        context = {
            'medical_record': medical_record,
            'user_attributes': user_attributes,
        }
        
        return render(request, 'medical_record_detail.html', context)
        
    except MedicalData.DoesNotExist:
        messages.error(request, 'Medical record không tồn tại.')
        return redirect('dashboard')

@login_required
@require_http_methods(["GET"])
def get_encrypted_medical_record(request, record_id):
    """API endpoint để lấy dữ liệu medical record đã mã hóa cho client-side decryption"""
    try:
        medical_record = MedicalData.objects.get(id=record_id)
        
        # Convert binary data to base64 for JSON transport
        import base64
        
        response_data = {
            'id': medical_record.id,
            'patient_id': medical_record.patient_id,  # Unencrypted
            'owner_user': medical_record.owner_user.email,
            'created_at': medical_record.created_at.isoformat(),
            'created_date': medical_record.created_date.isoformat(),
            
            # Patient info encrypted fields
            'patient_name_blob': base64.b64encode(medical_record.patient_name_blob).decode('utf-8') if medical_record.patient_name_blob else None,
            'patient_age_blob': base64.b64encode(medical_record.patient_age_blob).decode('utf-8') if medical_record.patient_age_blob else None,
            'patient_gender_blob': base64.b64encode(medical_record.patient_gender_blob).decode('utf-8') if medical_record.patient_gender_blob else None,
            'patient_phone_blob': base64.b64encode(medical_record.patient_phone_blob).decode('utf-8') if medical_record.patient_phone_blob else None,
            
            # Patient info AES key and IV (CP-ABE encrypted)
            'patient_info_aes_key_blob': base64.b64encode(medical_record.patient_info_aes_key_blob).decode('utf-8'),
            'patient_info_aes_iv_blob': base64.b64encode(medical_record.patient_info_aes_iv_blob).decode('utf-8'),
            
            # Medical record encrypted fields
            'chief_complaint_blob': base64.b64encode(medical_record.chief_complaint_blob).decode('utf-8') if medical_record.chief_complaint_blob else None,
            'past_medical_history_blob': base64.b64encode(medical_record.past_medical_history_blob).decode('utf-8') if medical_record.past_medical_history_blob else None,
            'diagnosis_blob': base64.b64encode(medical_record.diagnosis_blob).decode('utf-8') if medical_record.diagnosis_blob else None,
            'status_blob': base64.b64encode(medical_record.status_blob).decode('utf-8') if medical_record.status_blob else None,
            
            # Medical record AES key and IV (CP-ABE encrypted)
            'medical_record_aes_key_blob': base64.b64encode(medical_record.medical_record_aes_key_blob).decode('utf-8'),
            'medical_record_aes_iv_blob': base64.b64encode(medical_record.medical_record_aes_iv_blob).decode('utf-8'),
        }
        
        return JsonResponse({
            'success': True,
            'data': response_data
        })
        
    except MedicalData.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Medical record không tồn tại.'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Lỗi khi lấy dữ liệu: {str(e)}'
        }, status=500)