import base64
import os
from pathlib import Path
import pickle
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from charm.toolbox.pairinggroup import PairingGroup, GT
from charm.schemes.abenc.ac17 import AC17CPABE

from backend.models import *


if not isinstance(settings.BASE_DIR, Path):
    BASE_DIR_PATH = Path(settings.BASE_DIR)
else:
    BASE_DIR_PATH = settings.BASE_DIR

ABE_PARAMS_DIR = BASE_DIR_PATH / 'abe_params'
ABE_SECURE_KEYS_DIR = BASE_DIR_PATH / 'secure_keys'

PK_FILE_PATH = ABE_PARAMS_DIR / 'public_parameters.bin' # Bây giờ ABE_PARAMS_DIR là Path object
MSK_FILE_PATH = ABE_SECURE_KEYS_DIR / 'master_secret.key' # Bây giờ ABE_SECURE_KEYS_DIR là Path object


_charm_group = None
_charm_ac17_scheme = None
_loaded_pk = None
_loaded_msk = None



def init_charm_settings():
    """
    Khởi tạo đối tượng PairingGroup và AC17CPABE scheme.
    Hàm này nên được gọi một lần khi ứng dụng Django khởi động (ví dụ trong apps.py AppConfig.ready()).
    """
    global _charm_group, _charm_ac17_scheme
    if _charm_group is None:
        # Chọn một curve phù hợp. 'SS512' là một lựa chọn phổ biến cho 80-bit security.
        _charm_group = PairingGroup('SS512') # HOẶC 'MNT159', 'MNT224', ...
        # assump_size: Kích thước của linear assumption, ít nhất là 2 cho AC17.
        _charm_ac17_scheme = AC17CPABE(_charm_group, assump_size=2, verbose=False)
        print("Charm-Crypto Group and AC17 Scheme Initialized.")

def get_charm_group():
    if _charm_group is None:
        init_charm_settings()
    return _charm_group

def get_ac17_scheme():
    if _charm_ac17_scheme is None:
        init_charm_settings()
    return _charm_ac17_scheme


def deserialize_charm_object(group, serialized_object):
    """
    Deserialize một đối tượng Charm đã được serialize (có thể là dictionary chứa bytes).
    Chuyển đổi các bytes thành pairing.Element sử dụng group.deserialize().
    """
    if isinstance(serialized_object, dict):
        deserialized_dict = {}
        for key, value in serialized_object.items():
            deserialized_dict[key] = deserialize_charm_object(group, value)
        return deserialized_dict
    elif isinstance(serialized_object, list):
        return [deserialize_charm_object(group, item) for item in serialized_object]
    elif isinstance(serialized_object, bytes):
        # Đây là một pairing.Element đã được serialize thành bytes, deserialize nó
        # Cần kiểm tra xem có phải tất cả bytes đều là element không, hoặc có cờ nào đó không.
        # Giả định rằng nếu là bytes thì đó là element đã serialize.
        try:
            return group.deserialize(serialized_object)
        except Exception as e: # Bắt lỗi nếu deserialize không thành công
            # print(f"Warning: Could not deserialize bytes: {e}. Returning as bytes.")
            return serialized_object # Trả lại bytes nếu không deserialize được (có thể là giá trị khác)
    else:
        # Các kiểu dữ liệu khác (int, str) để nguyên
        return serialized_object


def load_public_parameters():
    global _loaded_pk
    if _loaded_pk is None:
        if not PK_FILE_PATH.exists():
            raise ImproperlyConfigured(f"PK file not found: {PK_FILE_PATH}. Run setup_abe_system.")
        with open(PK_FILE_PATH, 'rb') as f:
            serialized_pk = pickle.load(f) # Load dictionary chứa các bytes đã serialize
        group = get_charm_group() # Cần group để deserialize
        _loaded_pk = deserialize_charm_object(group, serialized_pk) # Deserialize các phần tử
    return _loaded_pk

def load_master_secret_key():
    global _loaded_msk
    if _loaded_msk is None:
        if not MSK_FILE_PATH.exists():
            raise ImproperlyConfigured(f"MSK file not found: {MSK_FILE_PATH}. Run setup_abe_system.")
        with open(MSK_FILE_PATH, 'rb') as f:
            serialized_msk = pickle.load(f) # Load dictionary chứa các bytes đã serialize
        group = get_charm_group() # Cần group để deserialize
        _loaded_msk = deserialize_charm_object(group, serialized_msk) # Deserialize các phần tử
    return _loaded_msk


def serialize_charm_object(group, charm_object):
    """
    Serialize một đối tượng Charm (có thể là dictionary chứa pairing.Element).
    Chuyển đổi tất cả các pairing.Element thành bytes sử dụng group.serialize().
    """
    if isinstance(charm_object, dict):
        serialized_dict = {}
        for key, value in charm_object.items():
            serialized_dict[key] = serialize_charm_object(group, value)
        return serialized_dict
    elif isinstance(charm_object, list):
        return [serialize_charm_object(group, item) for item in charm_object]
    else:
        # Thử serialize đối tượng bằng group.serialize()
        try:
            return group.serialize(charm_object)
        except (TypeError, AttributeError):
            # Nếu không serialize được, trả về nguyên đối tượng
            return charm_object

def generate_user_secret_key(user):
    """
    Generate CP-ABE secret key cho user dựa trên attributes của họ.
    
    Args:
        user: User object từ Django
        
    Returns:
        dict: Serialized secret key có thể gửi về client
    """
    try:
        # Load public parameters và master secret key
        pk = load_public_parameters()
        msk = load_master_secret_key()
        ac17_scheme = get_ac17_scheme()
        group = get_charm_group()
        
        # Lấy danh sách attributes của user
        from .models import UserAttribute
        user_attributes = UserAttribute.objects.filter(user=user)
        attr_list = [ua.attribute.name for ua in user_attributes]
        
        if not attr_list:
            raise ValueError(f"User {user.email} has no attributes assigned")
        
        print(f"Generating secret key for user {user.email} with attributes: {attr_list}")
        
        # Generate secret key bằng AC17 scheme
        secret_key = ac17_scheme.keygen(pk, msk, attr_list)
        
        # Serialize secret key để có thể gửi về client
        serialized_sk = serialize_charm_object(group, secret_key)
        
        # Convert bytes thành base64 để có thể JSON serialize
        json_compatible_sk = convert_bytes_to_base64(serialized_sk)
        
        return {
            'secret_key': json_compatible_sk,
            'attributes': attr_list,
            'user_email': user.email
        }
        
    except Exception as e:
        print(f"Error generating secret key for user {user.email}: {e}")
        raise

def convert_bytes_to_base64(obj):
    """
    Convert bytes objects trong nested dict/list thành base64 strings
    để có thể JSON serialize.
    """
    if isinstance(obj, dict):
        return {key: convert_bytes_to_base64(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_bytes_to_base64(item) for item in obj]
    elif isinstance(obj, bytes):
        return base64.b64encode(obj).decode('utf-8')
    else:
        return obj

def convert_base64_to_bytes(obj):
    """
    Convert base64 strings trong nested dict/list trở lại thành bytes
    để có thể deserialize Charm objects.
    """
    if isinstance(obj, dict):
        return {key: convert_base64_to_bytes(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_base64_to_bytes(item) for item in obj]
    elif isinstance(obj, str):
        try:
            # Thử decode base64, nếu không được thì giữ nguyên string
            return base64.b64decode(obj)
        except:
            return obj
    else:
        return obj

def get_public_parameters_for_client():
    """
    Lấy public parameters đã serialize để gửi về client.
    Client cần PK để encrypt dữ liệu.
    """
    try:
        pk = load_public_parameters()
        group = get_charm_group()
        
        # Serialize public parameters
        serialized_pk = serialize_charm_object(group, pk)
        
        # Convert thành JSON-compatible format
        json_compatible_pk = convert_bytes_to_base64(serialized_pk)
        
        return json_compatible_pk
        
    except Exception as e:
        print(f"Error getting public parameters for client: {e}")
        raise
    
    
# ==================== USER ATTRIBUTE FUNCTIONS ====================

def get_user_attributes_list(user):
    """
    Lấy danh sách attributes của user theo format CP-ABE
    
    Args:
        user: User object
        
    Returns:
        list: Danh sách attributes như ['patient', 'family_member:P1234567890', 'doctor']
        
    Example:
        user = User.objects.get(email='doctor@hospital.com')
        attrs = get_user_attributes_list(user)
        print(attrs)  # ['patient', 'doctor', 'physician', 'hospital_1']
    """
    user_attributes = UserAttribute.objects.filter(user=user).select_related('attribute')
    
    attributes_list = []
    for user_attr in user_attributes:
        attributes_list.append(user_attr.full_attribute_name)
    
    return attributes_list


def add_family_member(family_user, patient_user):
    """
    Thêm family_user làm thành viên gia đình của patient_user
    
    Args:
        family_user: User object (người sẽ trở thành family member)
        patient_user: User object (bệnh nhân)
        
    Returns:
        bool: True nếu tạo mới thành công, False nếu đã tồn tại hoặc lỗi
        
    Example:
        patient = User.objects.get(email='patient@example.com')
        family = User.objects.get(email='family@example.com')
        success = add_family_member(family, patient)
        if success:
            print("Đã thêm thành viên gia đình thành công")
    """
    try:
        family_attr = Attribute.objects.get(name='family_member')
        
        user_attr, created = UserAttribute.objects.get_or_create(
            user=family_user,
            attribute=family_attr,
            patient_id=patient_user.patient_id
        )
        
        if created:
            logger.info(f"Added {family_user.email} as family member of {patient_user.patient_id}")
        
        return created
        
    except Attribute.DoesNotExist:
        logger.error("Attribute 'family_member' does not exist")
        return False
    except Exception as e:
        logger.error(f"Error adding family member: {e}")
        return False


def remove_family_member(family_user, patient_user):
    """
    Xóa family_user khỏi danh sách thành viên gia đình của patient_user
    
    Args:
        family_user: User object
        patient_user: User object
        
    Returns:
        bool: True nếu xóa thành công
    """
    try:
        UserAttribute.objects.filter(
            user=family_user,
            attribute__name='family_member',
            patient_id=patient_user.patient_id
        ).delete()
        
        logger.info(f"Removed {family_user.email} from family of {patient_user.patient_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error removing family member: {e}")
        return False


def get_family_members_of_patient(patient_user):
    """
    Lấy danh sách family members của bệnh nhân
    
    Args:
        patient_user: User object (bệnh nhân)
        
    Returns:
        QuerySet: Danh sách User objects là family members
        
    Example:
        patient = User.objects.get(patient_id='P1234567890')
        family_members = get_family_members_of_patient(patient)
        for member in family_members:
            print(f"Family member: {member.email}")
    """
    return User.objects.filter(
        attributes_possessed__attribute__name='family_member',
        attributes_possessed__patient_id=patient_user.patient_id
    ).distinct()


def get_patients_of_family_member(family_user):
    """
    Lấy danh sách bệnh nhân mà user này là family member
    
    Args:
        family_user: User object
        
    Returns:
        QuerySet: Danh sách User objects là bệnh nhân
    """
    patient_ids = UserAttribute.objects.filter(
        user=family_user,
        attribute__name='family_member'
    ).values_list('patient_id', flat=True)
    
    return User.objects.filter(patient_id__in=patient_ids)


def add_user_attribute(user, attribute_name, patient_id=None):
    """
    Thêm attribute cho user
    
    Args:
        user: User object
        attribute_name: str (tên attribute)
        patient_id: str (optional, chỉ cho family_member)
        
    Returns:
        tuple: (UserAttribute object, created boolean)
        
    Example:
        # Thêm attribute doctor
        add_user_attribute(user, 'doctor')
        
        # Thêm family member
        add_user_attribute(family_user, 'family_member', patient_id='P1234567890')
    """
    try:
        attribute = Attribute.objects.get(name=attribute_name)
        
        user_attr, created = UserAttribute.objects.get_or_create(
            user=user,
            attribute=attribute,
            patient_id=patient_id
        )
        
        return user_attr, created
        
    except Attribute.DoesNotExist:
        logger.error(f"Attribute '{attribute_name}' does not exist")
        return None, False


# ==================== POLICY FUNCTIONS ====================

def get_applicable_policies_for_patient(patient_id):
    """
    Lấy danh sách policies có thể áp dụng cho bệnh nhân
    
    Args:
        patient_id: str (ID của bệnh nhân)
        
    Returns:
        list: Danh sách dict chứa thông tin policy
        
    Example:
        policies = get_applicable_policies_for_patient('P1234567890')
        for policy in policies:
            print(f"Policy: {policy['name']} -> {policy['rendered']}")
    """
    policies = []
    
    for policy in AccessPolicy.objects.all():
        if policy.is_applicable_for_patient(patient_id):
            try:
                rendered = policy.render_policy(patient_id=patient_id)
                policies.append({
                    'id': policy.id,
                    'name': policy.name,
                    'template': policy.policy_template,
                    'rendered': rendered,
                    'type': policy.policy_type,
                    'description': policy.description
                })
            except Exception as e:
                logger.error(f"Error rendering policy {policy.name}: {e}")
    
    return policies


def create_protected_data_with_policy(owner, policy_template, patient_id=None, 
                                    filename=None, mime_type=None, file_size=None,
                                    description=None, **policy_context):
    """
    Tạo ProtectedData object với policy template
    
    Args:
        owner: User object (chủ sở hữu data)
        policy_template: AccessPolicy object
        patient_id: str (optional)
        filename: str (optional)
        mime_type: str (optional)
        file_size: int (optional)
        description: str (optional)
        **policy_context: Các placeholder khác cho policy
        
    Returns:
        ProtectedData: Object đã tạo (chưa save)
        
    Example:
        policy = AccessPolicy.objects.get(name='Family Only')
        protected_data = create_protected_data_with_policy(
            owner=user,
            policy_template=policy,
            patient_id='P1234567890',
            filename='medical_report.pdf',
            mime_type='application/pdf'
        )
        # Sau đó client sẽ set encrypted data và save
    """
    try:
        # Render policy
        rendered_policy = policy_template.render_policy(
            patient_id=patient_id,
            **policy_context
        )
        
        # Tạo ProtectedData object
        protected_data = ProtectedData(
            owner_user=owner,
            policy_template=policy_template,
            target_patient_id=patient_id,
            rendered_policy=rendered_policy,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            description=description
        )
        
        return protected_data
        
    except Exception as e:
        logger.error(f"Error creating protected data: {e}")
        return None


def evaluate_policy_for_user(policy_string, user_attributes):
    """
    Đánh giá xem user có thỏa mãn policy không
    
    Đây là implementation đơn giản. Trong thực tế, bạn sẽ cần
    parser phức tạp hơn để xử lý các toán tử AND, OR, NOT.
    
    Args:
        policy_string: str (policy đã render, ví dụ: 'doctor OR family_member:P1234567890')
        user_attributes: list (danh sách attributes của user)
        
    Returns:
        bool: True nếu user thỏa mãn policy
        
    Example:
        policy = 'doctor OR family_member:P1234567890'
        user_attrs = ['patient', 'family_member:P1234567890']
        result = evaluate_policy_for_user(policy, user_attrs)
        print(result)  # True
    """
    try:
        # Implementation đơn giản cho demo
        # Trong production, cần parser phức tạp hơn
        
        # Xử lý OR
        if ' OR ' in policy_string:
            or_parts = policy_string.split(' OR ')
            return any(evaluate_policy_for_user(part.strip(), user_attributes) for part in or_parts)
        
        # Xử lý AND
        if ' AND ' in policy_string:
            and_parts = policy_string.split(' AND ')
            return all(evaluate_policy_for_user(part.strip(), user_attributes) for part in and_parts)
        
        # Xử lý NOT
        if policy_string.startswith('NOT '):
            inner_policy = policy_string[4:].strip()
            return not evaluate_policy_for_user(inner_policy, user_attributes)
        
        # Xử lý parentheses (đơn giản)
        if policy_string.startswith('(') and policy_string.endswith(')'):
            inner_policy = policy_string[1:-1].strip()
            return evaluate_policy_for_user(inner_policy, user_attributes)
        
        # Kiểm tra attribute đơn giản
        return policy_string.strip() in user_attributes
        
    except Exception as e:
        logger.error(f"Error evaluating policy '{policy_string}': {e}")
        return False


# ==================== UTILITY FUNCTIONS ====================

def get_user_accessible_data(user):
    """
    Lấy danh sách dữ liệu mà user có thể truy cập
    
    Args:
        user: User object
        
    Returns:
        QuerySet: Danh sách ProtectedData objects
    """
    user_attributes = get_user_attributes_list(user)
    accessible_data = []
    
    for data in ProtectedData.objects.all():
        if evaluate_policy_for_user(data.rendered_policy, user_attributes):
            accessible_data.append(data.id)
    
    return ProtectedData.objects.filter(id__in=accessible_data)


def get_patient_data_summary(patient_user):
    """
    Lấy tổng quan dữ liệu của bệnh nhân
    
    Args:
        patient_user: User object
        
    Returns:
        dict: Thông tin tổng quan
    """
    return {
        'patient_id': patient_user.patient_id,
        'patient_name': patient_user.get_full_name(),
        'total_files': ProtectedData.objects.filter(target_patient_id=patient_user.patient_id).count(),
        'family_members_count': get_family_members_of_patient(patient_user).count(),
        'user_attributes': get_user_attributes_list(patient_user)
    }


def validate_patient_id(patient_id):
    """
    Kiểm tra patient_id có hợp lệ không
    
    Args:
        patient_id: str
        
    Returns:
        bool: True nếu hợp lệ
    """
    if not patient_id:
        return False
    
    # Kiểm tra format (P + 10 ký tự)
    if not patient_id.startswith('P') or len(patient_id) != 11:
        return False
    
    # Kiểm tra tồn tại trong database
    return User.objects.filter(patient_id=patient_id).exists()