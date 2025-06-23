from rest_framework.permissions import BasePermission
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Khởi tạo Charm-Crypto components một lần
CHARM_GROUP_FOR_POLICY_CHECK = None
MSP_UTIL_FOR_POLICY_CHECK = None

try:
    from charm.toolbox.pairinggroup import PairingGroup
    from charm.toolbox.msp import MSP
    
    # Lấy tên nhóm từ settings
    pairing_group_name = getattr(settings, 'CPABE_PAIRING_GROUP', 'BN254')
    CHARM_GROUP_FOR_POLICY_CHECK = PairingGroup(pairing_group_name)
    MSP_UTIL_FOR_POLICY_CHECK = MSP(CHARM_GROUP_FOR_POLICY_CHECK, verbose=False)
    logger.info(f"Charm-Crypto PairingGroup '{pairing_group_name}' and MSP initialized for policy checking.")
except ImportError as e:
    logger.critical(f"CRITICAL: Failed to import Charm-Crypto: {e}. Install with 'pip install Charm-Crypto==0.50'")
except Exception as e:
    logger.critical(f"CRITICAL: Failed to initialize Charm-Crypto components for policy checking: {e}. ABAC based on CP-ABE policy will not work.")

class CanUploadTextDataPermission(BasePermission):
    """
    Permission để kiểm tra xem user có thể upload text data không
    Có thể mở rộng với ABAC logic trong tương lai
    """
    
    def has_permission(self, request, view):
        # Hiện tại chỉ cần user đã được authenticated
        return request.user and request.user.is_authenticated

class CanAccessEHRDataPermission(BasePermission):
    """
    Permission để kiểm tra xem user có thể truy cập EHR data không
    Có thể mở rộng với ABAC logic trong tương lai
    """
    
    def has_permission(self, request, view):
        # Hiện tại chỉ cần user đã được authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Kiểm tra permission cho object cụ thể
        Có thể implement logic ABAC ở đây
        """
        # Ví dụ: chỉ cho phép user truy cập data mà họ đã tạo
        # hoặc theo policy ABAC phức tạp hơn
        return True  # Tạm thời cho phép tất cả 

class SatisfiesCPABEPolicyPermission(BasePermission):
    """
    Permission class để kiểm tra xem thuộc tính CP-ABE của người dùng 
    có thỏa mãn chính sách được lưu trữ cùng dữ liệu hay không
    """
    message = "Thuộc tính của bạn không thỏa mãn chính sách truy cập của dữ liệu này."

    def has_object_permission(self, request, view, obj):
        """
        Kiểm tra quyền trên một đối tượng 'obj' cụ thể (là instance của ProtectedEHRTextData).
        'obj' phải có thuộc tính 'cpabe_policy_applied'.
        """
        # Bước 1: Kiểm tra các điều kiện cơ bản
        if not request.user or not request.user.is_authenticated:
            logger.warning(f"User không được authenticated trong SatisfiesCPABEPolicyPermission: user={request.user}")
            return False
            
        if not hasattr(request, 'auth') or not request.auth:
            logger.warning(f"request.auth không tồn tại trong SatisfiesCPABEPolicyPermission: hasattr={hasattr(request, 'auth')}, auth={getattr(request, 'auth', 'None')}")
            return False
            
        if not CHARM_GROUP_FOR_POLICY_CHECK or not MSP_UTIL_FOR_POLICY_CHECK:
            logger.error(f"Thành phần Charm-Crypto (Group/MSP) chưa được khởi tạo. Group={CHARM_GROUP_FOR_POLICY_CHECK}, MSP={MSP_UTIL_FOR_POLICY_CHECK}")
            # Quyết định hành vi: an toàn nhất là từ chối
            self.message = "Lỗi hệ thống: Không thể xác minh chính sách truy cập."
            return False

        # Bước 2: Lấy thuộc tính CP-ABE của người dùng từ JWT
        token_payload = request.auth.payload
        
        # Đọc từ user_attributes thay vì cpabe_ids (theo JWT payload thực tế)
        user_cpabe_ids_str = token_payload.get('user_attributes', "")  # Đọc từ user_attributes
        
        user_attributes_list_for_charm = []  # Charm MSP thường làm việc với list các string thuộc tính
        if user_cpabe_ids_str:
            user_attributes_list_for_charm = [
                attr.strip() for attr in user_cpabe_ids_str.split(',') if attr.strip()
            ]
        
        if not user_attributes_list_for_charm:
            logger.warning(f"User {request.user.id} không có thuộc tính CP-ABE nào trong token.")
            self.message = "Bạn không có thuộc tính CP-ABE nào để đối chiếu với chính sách."
            return False
            
        logger.debug(f"User {request.user.id} CP-ABE attributes for policy check: {user_attributes_list_for_charm}")

        # Bước 3: Lấy chuỗi policy CP-ABE của đối tượng dữ liệu 'obj'
        if not hasattr(obj, 'cpabe_policy_applied') or not obj.cpabe_policy_applied:
            logger.warning(f"Resource (ID: {getattr(obj, 'id', 'N/A')}) không có 'cpabe_policy_applied'. Mặc định từ chối.")
            self.message = "Dữ liệu không có chính sách truy cập CP-ABE được định nghĩa."
            return False
        
        resource_cpabe_policy_string = obj.cpabe_policy_applied
        logger.debug(f"Checking policy for resource (ID: {getattr(obj, 'id', 'N/A')}): '{resource_cpabe_policy_string}' "
                     f"against user attributes {user_attributes_list_for_charm}")

        # Bước 4: Kiểm tra CP-ABE policy toàn diện sử dụng MSP evaluation
        try:
            logger.info(f"Starting comprehensive CP-ABE policy evaluation:")
            logger.info(f"  Resource policy: '{resource_cpabe_policy_string}'")
            logger.info(f"  User attributes: {user_attributes_list_for_charm}")
            
            # 4.1. Parse policy string thành policy tree
            policy_object = MSP_UTIL_FOR_POLICY_CHECK.createPolicy(resource_cpabe_policy_string)
            logger.info(f"  Policy object created: {type(policy_object)}")
            
            # 4.2. Sử dụng MSP.prune() để kiểm tra toàn diện
            # prune() trả về False nếu không satisfy, hoặc subset attributes nếu satisfy
            satisfied_attributes = MSP_UTIL_FOR_POLICY_CHECK.prune(policy_object, user_attributes_list_for_charm)
            
            logger.info(f"  MSP.prune() result: {satisfied_attributes}")
            logger.info(f"  MSP.prune() type: {type(satisfied_attributes)}")
            
            if satisfied_attributes is not False and satisfied_attributes is not None:
                # Policy được thỏa mãn
                logger.info(f"✅ Policy '{resource_cpabe_policy_string}' SATISFIED by user attributes "
                            f"{user_attributes_list_for_charm}")
                logger.info(f"  Satisfying subset: {satisfied_attributes}")
                return True
            else:
                # Policy không được thỏa mãn - tìm hiểu nguyên nhân
                all_policy_attributes = MSP_UTIL_FOR_POLICY_CHECK.getAttributeList(policy_object)
                user_attrs_set = set(user_attributes_list_for_charm)
                policy_attrs_set = set(all_policy_attributes)
                
                logger.warning(f"❌ Policy '{resource_cpabe_policy_string}' NOT SATISFIED")
                logger.info(f"  All policy attributes: {all_policy_attributes}")
                logger.info(f"  User has: {user_attrs_set}")
                logger.info(f"  Policy requires: {policy_attrs_set}")
                
                missing_attrs = policy_attrs_set - user_attrs_set
                if missing_attrs:
                    self.message = f"Thiếu thuộc tính: {', '.join(missing_attrs)}. Policy cần: {resource_cpabe_policy_string}"
                else:
                    self.message = f"Thuộc tính không thỏa mãn cấu trúc policy: {resource_cpabe_policy_string}"
                
                return False
        except Exception as e:
            logger.error(f"Lỗi khi đánh giá policy CP-ABE '{resource_cpabe_policy_string}' "
                         f"cho resource (ID: {getattr(obj, 'id', 'N/A')}) với thuộc tính {user_attributes_list_for_charm}: {e}")
            # Trong trường hợp lỗi phân tích policy hoặc lỗi không mong muốn, an toàn nhất là từ chối
            self.message = "Lỗi hệ thống khi xác minh chính sách truy cập dữ liệu."
            return False

    def has_permission(self, request, view):
        # Phương thức này được gọi cho các action không có đối tượng cụ thể (ví dụ: list, create).
        # Trong trường hợp này, chúng ta không có 'obj' để lấy 'cpabe_policy_applied'.
        # Nếu bạn muốn kiểm tra quyền chung ở đây (ví dụ: user phải có vai trò 'DATA_VIEWER'),
        # bạn có thể làm tương tự như HasABACAttributes đã thảo luận trước,
        # dựa trên các claim ABAC chung trong JWT (ví dụ: 'roles').
        # Đối với việc kiểm tra policy CP-ABE cụ thể, nó phải là object-level.
        if hasattr(view, 'action') and view.action in ['list', 'create']:
            # logger.debug(f"Skipping CP-ABE policy check for '{view.action}' action.")
            return True  # Hoặc triển khai logic ABAC chung ở đây nếu cần
        return True  # Mặc định cho phép, has_object_permission sẽ là nơi kiểm tra chính 