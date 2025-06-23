from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from django.conf import settings
from django.urls import reverse, NoReverseMatch
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import ProtectedEHRTextData
from .serializers import ProtectedEHRTextDataCreateSerializer, ProtectedEHRTextDataResponseSerializer
from .permissions import SatisfiesCPABEPolicyPermission, CHARM_GROUP_FOR_POLICY_CHECK, MSP_UTIL_FOR_POLICY_CHECK
from django.http import Http404
import logging

# Logger cho Resource API App
logger = logging.getLogger(__name__)


def login_page_on_main_server_view(request):
    auth_center_login_api_url = getattr(settings, 'AUTH_CENTER_LOGIN_API_URL', None)
    if not auth_center_login_api_url:
        pass
    context = {
        'auth_center_login_api_url': auth_center_login_api_url
    }
    return render(request, 'login.html', context)

def home_view(request):
    # Lấy URL từ settings hoặc đặt giá trị mặc định
    auth_center_pk_url = getattr(settings, 'AUTH_CENTER_PUBLIC_KEY_API_URL', 'http://localhost:8000/api/cpabe/public-key/')
    auth_center_sk_url = getattr(settings, 'AUTH_CENTER_SECRET_KEY_API_URL', 'http://localhost:8000/api/cpabe/generate-secret-key/')
    auth_center_logout_url = getattr(settings, 'AUTH_CENTER_LOGOUT_API_URL', 'http://localhost:8000/api/auth/logout/')


    # Lấy URL cho các trang trên Main Server bằng reverse
    try:
        # Giả sử bạn đã đặt 'name' cho các URL pattern này trong resource_api_app.urls
        main_server_upload_url = reverse('resource_api_app:rs_upload_page')
        main_server_decrypt_url = reverse('resource_api_app:rs_decrypt_page')
        main_server_login_url = reverse('resource_api_app:rs_login_page')
    except NoReverseMatch:
        # Fallback nếu URL name không tìm thấy (ví dụ, chưa định nghĩa)
        main_server_upload_url = '/accounts/upload/' # URL mặc định
        main_server_decrypt_url = '/accounts/decrypt/' # URL mặc định
        main_server_login_url = '/accounts/login/'   # URL mặc định
        print("CẢNH BÁO: Không tìm thấy URL name cho rs_upload_page, rs_decrypt_page hoặc rs_login_page. Sử dụng URL mặc định.")


    context = {
        'auth_center_public_key_api_url': auth_center_pk_url,
        'auth_center_secret_key_api_url': auth_center_sk_url,
        'auth_center_logout_api_url': auth_center_logout_url,
        'main_server_upload_page_url': main_server_upload_url,
        'main_server_decrypt_page_url': main_server_decrypt_url,
        'main_server_login_page_url': main_server_login_url,
    }
    return render(request, 'home.html', context)

def upload_document_page_view(request):
    return render(request, 'upload_document.html')

def decrypt_document_page_view(request):
    """
    View để hiển thị trang tìm kiếm bản ghi theo patient_id
    """
    return render(request, 'decrypt_document.html')


def decrypt_record_page_view(request, record_id):
    """
    View để hiển thị trang decrypt một bản ghi cụ thể.
    Không kiểm tra CP-ABE policy ở đây nữa - để JavaScript xử lý.
    Chỉ hiển thị trang và để JavaScript kiểm tra quyền truy cập.
    """
    logger.info(f"decrypt_record_page_view called for record_id: {record_id}")
    
    # Không cần kiểm tra JWT ở đây, để JavaScript xử lý
    # Vì token được lưu trong localStorage
    context = {
        'record_id': record_id
    }
    return render(request, 'decrypt_record.html', context)


def error_access_denied_view(request):
    """
    View để hiển thị error page khi không có quyền truy cập CP-ABE
    """
    error_message = request.GET.get('message', 'Bạn không có quyền truy cập tài nguyên này.')
    record_id = request.GET.get('record_id', '')
    
    context = {
        'error_title': 'Không Có Quyền Truy Cập',
        'error_message': 'Thuộc tính CP-ABE của bạn không thỏa mãn chính sách truy cập của dữ liệu này.',
        'error_details': error_message,
        'back_url': '/decrypt/',
        'record_id': record_id
    }
    return render(request, 'error_access_denied.html', context)


# API View để test JWT authentication
class TestAuthView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        API endpoint để test JWT authentication từ Auth Center và hiển thị parsed attributes
        """
        user = request.user
        
        # Parse user attributes thành dictionary nếu có
        parsed_attributes = {}
        if hasattr(user, 'user_attributes') and user.user_attributes:
            try:
                # Format: "role:doctor;department:cardiology;clearance:level2"
                attributes_pairs = user.user_attributes.split(';')
                for pair in attributes_pairs:
                    if ':' in pair:
                        key, value = pair.split(':', 1)
                        parsed_attributes[key.strip()] = value.strip()
            except Exception as e:
                logger.warning(f"Error parsing user attributes: {e}")
        
        # Lấy CP-ABE IDs từ JWT token (đọc từ user_attributes)
        cpabe_ids_str = ""
        cpabe_ids_list = []
        if hasattr(request, 'auth') and request.auth and hasattr(request.auth, 'payload'):
            cpabe_ids_str = request.auth.payload.get('user_attributes', '')
            if cpabe_ids_str:
                cpabe_ids_list = [attr.strip() for attr in cpabe_ids_str.split(',') if attr.strip()]
        
        user_info = {
            'user_id': user.id,
            'username': getattr(user, 'username', 'unknown'),
            'email': getattr(user, 'email', ''),
            'raw_user_attributes': getattr(user, 'user_attributes', ''),
            'parsed_attributes': parsed_attributes,
            'cpabe_ids_raw': cpabe_ids_str,
            'cpabe_ids_list': cpabe_ids_list,
            'is_authenticated': user.is_authenticated,
        }
        
        logger.info(f"Auth Center token successfully parsed for user: {user_info['username']} with CP-ABE IDs: {cpabe_ids_list}")
        
        return Response({
            'message': 'Auth Center JWT token successfully authenticated and parsed',
            'user_info': user_info,
            'attributes_count': len(parsed_attributes),
            'cpabe_attributes_count': len(cpabe_ids_list),
            'server_info': 'Resource Server - Main Server Project'
        }, status=status.HTTP_200_OK)


class DebugCPABEView(APIView):
    """
    API endpoint để debug CP-ABE policy checking
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, entry_id_uuid):
        """
        Debug API để xem thông tin chi tiết về CP-ABE policy checking
        """
        try:
            # Lấy bản ghi EHR
            ehr_entry = ProtectedEHRTextData.objects.get(id=entry_id_uuid)
            
            # Lấy thông tin user từ JWT
            user = request.user
            token_payload = request.auth.payload if hasattr(request, 'auth') and request.auth else {}
            
            # Lấy CP-ABE IDs từ JWT token (đọc từ user_attributes)
            user_cpabe_ids_str = token_payload.get('user_attributes', '')
            user_attributes_list = []
            if user_cpabe_ids_str:
                user_attributes_list = [attr.strip() for attr in user_cpabe_ids_str.split(',') if attr.strip()]
            
            # Thông tin debug
            debug_info = {
                'user_id': user.id,
                'username': getattr(user, 'username', 'unknown'),
                'ehr_entry_id': str(ehr_entry.id),
                'ehr_policy': ehr_entry.cpabe_policy_applied,
                'user_cpabe_ids_raw': user_cpabe_ids_str,
                'user_cpabe_ids_list': user_attributes_list,
                'jwt_payload': token_payload,
                'permission_check_result': None,
                'permission_error': None
            }
            
            # Thử kiểm tra permission
            try:
                from .permissions import SatisfiesCPABEPolicyPermission
                permission_checker = SatisfiesCPABEPolicyPermission()
                
                # Kiểm tra has_object_permission
                permission_result = permission_checker.has_object_permission(request, None, ehr_entry)
                debug_info['permission_check_result'] = permission_result
                debug_info['permission_message'] = permission_checker.message if not permission_result else "Access granted"
                
                if permission_result:
                    debug_info['access_status'] = 'ALLOWED'
                else:
                    debug_info['access_status'] = 'DENIED'
                    
            except Exception as e:
                debug_info['permission_error'] = str(e)
                debug_info['access_status'] = 'ERROR'
            
            return Response({
                'debug_info': debug_info,
                'charm_crypto_status': {
                    'group_initialized': CHARM_GROUP_FOR_POLICY_CHECK is not None,
                    'msp_initialized': MSP_UTIL_FOR_POLICY_CHECK is not None
                }
            }, status=status.HTTP_200_OK)
            
        except ProtectedEHRTextData.DoesNotExist:
            return Response({"error": "Không tìm thấy bản ghi EHR."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Debug CP-ABE error: {e}")
            return Response({"error": f"Debug error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UploadEHRTextView(APIView):
    permission_classes = [IsAuthenticated] # Chỉ user đã đăng nhập mới được upload
    # permission_classes = [IsAuthenticated, CanUploadTextDataPermission] # Nếu bạn có permission ABAC

    def post(self, request):
        user_id_from_token = request.user.id # Lấy từ JWT đã được xác thực

        # Sử dụng serializer để validate và tạo đối tượng
        # request.data sẽ là JSON payload từ client
        serializer = ProtectedEHRTextDataCreateSerializer(data=request.data)

        if serializer.is_valid():
            try:
                # Gán created_by_ac_user_id trước khi lưu
                ehr_entry = serializer.save(created_by_ac_user_id=user_id_from_token)
                
                # Trả về thông tin cơ bản của entry đã tạo (không bao gồm nội dung mã hóa)
                response_serializer = ProtectedEHRTextDataResponseSerializer(ehr_entry)
                logger.info(f"User {user_id_from_token} đã upload thành công EHR text entry ID: {ehr_entry.id}")
                return Response({
                    "message": "Dữ liệu văn bản đã được lưu trữ thành công.",
                    "entry_id": ehr_entry.id,
                    "data": response_serializer.data
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                logger.error(f"Lỗi khi lưu ProtectedEHRTextData cho user {user_id_from_token}: {e}")
                return Response({"error": "Lỗi phía server khi lưu trữ dữ liệu."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            logger.warning(f"Dữ liệu upload từ user {user_id_from_token} không hợp lệ: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RetrieveEHRTextView(APIView):
    """
    API View để lấy chi tiết một ProtectedEHRTextData với kiểm tra CP-ABE policy
    View này sẽ trả về các trường đã mã hóa để client tự giải mã.
    """
    permission_classes = [IsAuthenticated, SatisfiesCPABEPolicyPermission]

    def get_object(self, entry_id_uuid):
        """
        Lấy object EHR entry theo ID, cần thiết cho object-level permission checking
        """
        try:
            return ProtectedEHRTextData.objects.get(id=entry_id_uuid)
        except ProtectedEHRTextData.DoesNotExist:
            raise Http404

    def get(self, request, entry_id_uuid):
        """
        Lấy chi tiết một bản ghi EHR đã mã hóa.
        Trước khi trả về, kiểm tra xem thuộc tính CP-ABE của user có thỏa mãn 
        chính sách được lưu trữ cùng dữ liệu hay không.
        """
        ehr_entry = self.get_object(entry_id_uuid)
        
        # Kiểm tra object-level permission (SatisfiesCPABEPolicyPermission.has_object_permission)
        # Django REST Framework sẽ tự động gọi has_object_permission khi có object
        self.check_object_permissions(request, ehr_entry)
        
        # Nếu đến được đây, SatisfiesCPABEPolicyPermission.has_object_permission đã trả về True
        
        # Chuẩn bị dữ liệu để trả về cho client (bao gồm các phần đã mã hóa)
        data_to_return = {
            'id': str(ehr_entry.id),  # Chuyển UUID thành string
            'patient_id_on_rs': ehr_entry.patient_id_on_rs,
            'description': ehr_entry.description,
            'data_type': ehr_entry.data_type,
            'cpabe_policy_applied': ehr_entry.cpabe_policy_applied,
            'encrypted_kek_b64': ehr_entry.encrypted_kek_b64,
            'aes_iv_b64': ehr_entry.aes_iv_b64,
            'encrypted_main_content_b64': ehr_entry.encrypted_main_content_b64,
            'created_at': ehr_entry.created_at.isoformat()  # Định dạng ISO cho datetime
        }
        
        logger.info(f"User {request.user.id} được phép truy cập ciphertext của EHR entry ID: {ehr_entry.id} "
                   f"(Policy CP-ABE '{ehr_entry.cpabe_policy_applied}' đã được kiểm tra phía server)")
        
        return Response(data_to_return)


class ListEHRByPatientView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, patient_id):
        """
        API để lấy danh sách tất cả bản ghi EHR của một patient
        """
        try:
            # Lấy tất cả bản ghi của patient này
            ehr_entries = ProtectedEHRTextData.objects.filter(
                patient_id_on_rs=patient_id
            ).order_by('-created_at')
            
            if not ehr_entries.exists():
                return Response({
                    "message": f"Không tìm thấy bản ghi nào cho bệnh nhân {patient_id}",
                    "patient_id": patient_id,
                    "records": []
                }, status=status.HTTP_200_OK)
            
            # Tạo danh sách bản ghi (không bao gồm nội dung mã hóa để giảm payload)
            records_list = []
            for entry in ehr_entries:
                records_list.append({
                    'id': entry.id,
                    'description': entry.description,
                    'data_type': entry.data_type,
                    'cpabe_policy_applied': entry.cpabe_policy_applied,
                    'created_at': entry.created_at,
                    'updated_at': entry.updated_at,
                    'created_by_ac_user_id': entry.created_by_ac_user_id
                })
            
            logger.info(f"User {request.user.id} accessed {len(records_list)} records for patient {patient_id}")
            
            return Response({
                "message": f"Tìm thấy {len(records_list)} bản ghi cho bệnh nhân {patient_id}",
                "patient_id": patient_id,
                "total_records": len(records_list),
                "records": records_list
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách EHR cho patient {patient_id}: {e}")
            return Response({"error": "Lỗi phía server."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)