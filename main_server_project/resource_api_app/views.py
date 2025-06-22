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
    View để hiển thị trang decrypt một bản ghi cụ thể
    """
    context = {
        'record_id': record_id
    }
    return render(request, 'decrypt_record.html', context)


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
        
        user_info = {
            'user_id': user.id,
            'username': getattr(user, 'username', 'unknown'),
            'email': getattr(user, 'email', ''),
            'raw_user_attributes': getattr(user, 'user_attributes', ''),
            'parsed_attributes': parsed_attributes,
            'is_authenticated': user.is_authenticated,
        }
        
        logger.info(f"Auth Center token successfully parsed for user: {user_info['username']}")
        
        return Response({
            'message': 'Auth Center JWT token successfully authenticated and parsed',
            'user_info': user_info,
            'attributes_count': len(parsed_attributes),
            'server_info': 'Resource Server - Main Server Project'
        }, status=status.HTTP_200_OK)


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

# TODO: Tạo API View để lấy danh sách hoặc chi tiết một ProtectedEHRTextData
# View này sẽ trả về các trường đã mã hóa để client tự giải mã.
class RetrieveEHRTextView(APIView):
    permission_classes = [IsAuthenticated] # Thêm permission ABAC nếu cần

    def get(self, request, entry_id_uuid): # Giả sử entry_id là UUID
        try:
            ehr_entry = ProtectedEHRTextData.objects.get(id=entry_id_uuid)
            # TODO: Áp dụng ABAC permission ở đây nếu cần, ví dụ:
            # if not user_can_access_this_specific_entry(request.user, request.auth.payload, ehr_entry):
            #     return Response({"error": "Không có quyền truy cập bản ghi này."}, status=status.HTTP_403_FORBIDDEN)

            # Trả về tất cả các trường cần thiết cho client giải mã
            data_to_return = {
                'id': ehr_entry.id,
                'patient_id_on_rs': ehr_entry.patient_id_on_rs,
                'description': ehr_entry.description,
                'data_type': ehr_entry.data_type,
                'cpabe_policy_applied': ehr_entry.cpabe_policy_applied,
                'encrypted_kek_b64': ehr_entry.encrypted_kek_b64,
                'aes_iv_b64': ehr_entry.aes_iv_b64,
                'encrypted_main_content_b64': ehr_entry.encrypted_main_content_b64,
                'created_at': ehr_entry.created_at
            }
            return Response(data_to_return)
        except ProtectedEHRTextData.DoesNotExist:
            return Response({"error": "Không tìm thấy bản ghi EHR."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Lỗi khi truy xuất EHR text entry {entry_id_uuid}: {e}")
            return Response({"error": "Lỗi phía server."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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