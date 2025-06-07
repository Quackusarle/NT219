import base64
import os
from pathlib import Path
import pickle
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from charm.toolbox.pairinggroup import PairingGroup, GT
from charm.schemes.abenc.waters11 import Waters11

from backend.models import *

# Constants
if not isinstance(settings.BASE_DIR, Path):
    BASE_DIR_PATH = Path(settings.BASE_DIR)
else:
    BASE_DIR_PATH = settings.BASE_DIR

ABE_PARAMS_DIR = BASE_DIR_PATH / 'abe_params'
ABE_SECURE_KEYS_DIR = BASE_DIR_PATH / 'secure_keys'
PK_FILE_PATH = ABE_PARAMS_DIR / 'public_parameters.bin'
MSK_FILE_PATH = ABE_SECURE_KEYS_DIR / 'master_secret.key'

# Global variables
_charm_group = None
_charm_waters11_scheme = None
_loaded_pk = None
_loaded_msk = None

# ==================== WATERS11 INITIALIZATION ====================

def init_charm_settings():
    """Khởi tạo đối tượng PairingGroup và Waters11 scheme"""
    global _charm_group, _charm_waters11_scheme
    if _charm_group is None:
        _charm_group = PairingGroup('SS512')
        _charm_waters11_scheme = Waters11(_charm_group, uni_size=1000, verbose=False)
        print("Charm-Crypto Group and Waters11 Scheme Initialized.")

def get_charm_group():
    if _charm_group is None:
        init_charm_settings()
    return _charm_group

def get_waters11_scheme():
    if _charm_waters11_scheme is None:
        init_charm_settings()
    return _charm_waters11_scheme

# ==================== ATTRIBUTE MAPPING FUNCTIONS ====================

def get_attribute_mapping():
    """Tạo mapping giữa attribute names và integers cho Waters11 scheme"""
    from .models import Attribute
    
    all_attributes = Attribute.objects.all().order_by('id')
    name_to_int = {}
    int_to_name = {}
    
    # Bắt đầu từ 1 vì Waters11 sử dụng h[0] cho mục đích khác
    for i, attr in enumerate(all_attributes, start=1):
        name_to_int[attr.name] = i
        int_to_name[i] = attr.name
    
    return name_to_int, int_to_name

def convert_attributes_to_integers(attr_names):
    """Chuyển đổi danh sách attribute names thành integers"""
    name_to_int, _ = get_attribute_mapping()
    
    attr_integers = []
    for attr_name in attr_names:
        if attr_name in name_to_int:
            attr_integers.append(name_to_int[attr_name])
        else:
            # Nếu attribute chưa có trong mapping, tạo mới
            from .models import Attribute
            attr_obj, created = Attribute.objects.get_or_create(name=attr_name)
            if created:
                # Refresh mapping
                name_to_int, _ = get_attribute_mapping()
            attr_integers.append(name_to_int[attr_name])
    
    return attr_integers

def convert_integers_to_attributes(attr_integers):
    """Chuyển đổi danh sách integers thành attribute names"""
    _, int_to_name = get_attribute_mapping()
    
    attr_names = []
    for attr_int in attr_integers:
        if attr_int in int_to_name:
            attr_names.append(int_to_name[attr_int])
        else:
            attr_names.append(str(attr_int))
    
    return attr_names

# ==================== KEY MANAGEMENT ====================

def load_public_parameters():
    global _loaded_pk
    if _loaded_pk is None:
        if not PK_FILE_PATH.exists():
            raise ImproperlyConfigured(f"PK file not found: {PK_FILE_PATH}")
        with open(PK_FILE_PATH, 'rb') as f:
            serialized_pk = pickle.load(f)
        group = get_charm_group()
        _loaded_pk = deserialize_charm_object(group, serialized_pk)
    return _loaded_pk

def load_master_secret_key():
    global _loaded_msk
    if _loaded_msk is None:
        if not MSK_FILE_PATH.exists():
            raise ImproperlyConfigured(f"MSK file not found: {MSK_FILE_PATH}")
        with open(MSK_FILE_PATH, 'rb') as f:
            serialized_msk = pickle.load(f)
        group = get_charm_group()
        _loaded_msk = deserialize_charm_object(group, serialized_msk)
    return _loaded_msk

# ==================== SERIALIZATION FUNCTIONS ====================

def serialize_charm_object(group, charm_object):
    """Serialize một đối tượng Charm"""
    if isinstance(charm_object, dict):
        serialized_dict = {}
        for key, value in charm_object.items():
            serialized_dict[key] = serialize_charm_object(group, value)
        return serialized_dict
    elif isinstance(charm_object, list):
        return [serialize_charm_object(group, item) for item in charm_object]
    else:
        try:
            # Try to serialize with group.serialize() first - this will work for all Charm Element objects
            return group.serialize(charm_object)
        except (TypeError, AttributeError, Exception):
            # If serialization fails, check if it's a basic Python type
            if isinstance(charm_object, (str, int, float, bool, type(None))):
                return charm_object
            else:
                # Log warning for debugging and try to convert to string as fallback
                print(f"Warning: Could not serialize object of type {type(charm_object)}: {charm_object}")
                try:
                    return str(charm_object)
                except:
                    return f"<unserializable_{type(charm_object).__name__}>"

def deserialize_charm_object(group, serialized_object):
    """Deserialize một đối tượng Charm"""
    if isinstance(serialized_object, dict):
        deserialized_dict = {}
        for key, value in serialized_object.items():
            deserialized_dict[key] = deserialize_charm_object(group, value)
        return deserialized_dict
    elif isinstance(serialized_object, list):
        return [deserialize_charm_object(group, item) for item in serialized_object]
    elif isinstance(serialized_object, bytes):
        try:
            return group.deserialize(serialized_object)
        except Exception as e:
            return serialized_object
    else:
        return serialized_object

# ==================== USER KEY GENERATION ====================

def generate_user_secret_key(user):
    """Generate CP-ABE secret key cho user dựa trên static attributes"""
    try:
        pk = load_public_parameters()
        msk = load_master_secret_key()
        waters11_scheme = get_waters11_scheme()
        group = get_charm_group()
        
        # Lấy danh sách static attributes của user
        from .models import UserAttribute
        user_attributes = UserAttribute.objects.filter(user=user)
        attr_names = [ua.attribute.name for ua in user_attributes]
        
        if not attr_names:
            raise ValueError(f"User {user.email} has no attributes assigned")
        
        # Chuyển đổi attribute names thành integers cho Waters11
        attr_integers = convert_attributes_to_integers(attr_names)
        
        print(f"Generating secret key for user {user.email} with attributes: {attr_names} -> {attr_integers}")
        
        # Generate secret key bằng Waters11 scheme
        secret_key = waters11_scheme.keygen(pk, msk, attr_integers)
        
        # Serialize secret key
        serialized_sk = serialize_charm_object(group, secret_key)
        json_compatible_sk = convert_bytes_to_base64(serialized_sk)
        
        return {
            'secret_key': json_compatible_sk,
            'attributes': attr_names,
            'attribute_integers': attr_integers,
            'user_email': user.email
        }
        
    except Exception as e:
        print(f"Error generating secret key for user {user.email}: {e}")
        raise

# ==================== CLIENT SUPPORT ====================

def convert_bytes_to_base64(obj):
    """Convert bytes objects thành base64 strings để JSON serialize"""
    if isinstance(obj, dict):
        return {key: convert_bytes_to_base64(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_bytes_to_base64(item) for item in obj]
    elif isinstance(obj, bytes):
        return base64.b64encode(obj).decode('utf-8')
    else:
        return obj

def convert_base64_to_bytes(obj):
    """Convert base64 strings trở lại thành bytes"""
    if isinstance(obj, dict):
        return {key: convert_base64_to_bytes(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_base64_to_bytes(item) for item in obj]
    elif isinstance(obj, str):
        try:
            return base64.b64decode(obj)
        except:
            return obj
    else:
        return obj

def get_public_parameters_for_client():
    """Lấy public parameters để gửi về client"""
    try:
        pk = load_public_parameters()
        group = get_charm_group()
        
        serialized_pk = serialize_charm_object(group, pk)
        json_compatible_pk = convert_bytes_to_base64(serialized_pk)
        
        name_to_int, int_to_name = get_attribute_mapping()
        
        return {
            'public_key': json_compatible_pk,
            'attribute_mapping': {
                'name_to_int': name_to_int,
                'int_to_name': int_to_name
            },
            'scheme_info': {
                'type': 'waters11',
                'uni_size': get_waters11_scheme().uni_size
            }
        }
        
    except Exception as e:
        print(f"Error getting public parameters for client: {e}")
        raise

# ==================== USER ATTRIBUTE FUNCTIONS ====================

def get_user_attributes_list(user, as_integers=False):
    """Lấy danh sách static attributes của user"""
    user_attributes = UserAttribute.objects.filter(user=user).select_related('attribute')
    attributes_list = [ua.attribute.name for ua in user_attributes]
    
    if as_integers:
        return convert_attributes_to_integers(attributes_list)
    
    return attributes_list

def add_user_attribute(user, attribute_name):
    """Thêm static attribute cho user"""
    try:
        attribute = Attribute.objects.get(name=attribute_name)
        user_attr, created = UserAttribute.objects.get_or_create(
            user=user,
            attribute=attribute
        )
        return user_attr, created
    except Attribute.DoesNotExist:
        return None, False

# ==================== POLICY EVALUATION ====================

def evaluate_policy_for_user(policy_string, user_attributes):
    """
    Đánh giá xem user có thỏa mãn policy không
    
    Policy Syntax:
    - AND: doctor AND nurse  
    - OR: doctor OR nurse
    - NOT: NOT doctor
    - Parentheses: (doctor OR nurse) AND hospital_1
    - Nested: doctor OR (nurse AND hospital_1)
    
    Args:
        policy_string: str (ví dụ: 'doctor OR (hospital_1 AND nurse)')
        user_attributes: list (danh sách attributes của user)
        
    Returns:
        bool: True nếu user thỏa mãn policy
    """
    try:
        return _evaluate_policy_recursive(policy_string.strip(), user_attributes)
    except Exception as e:
        print(f"Error evaluating policy '{policy_string}': {e}")
        return False

def _evaluate_policy_recursive(policy, user_attributes):
    """Recursive policy evaluation với proper precedence"""
    policy = policy.strip()
    
    # Base case: single attribute
    if not any(op in policy for op in [' OR ', ' AND ', 'NOT ', '(', ')']):
        return policy in user_attributes
    
    # Handle NOT
    if policy.startswith('NOT '):
        inner_policy = policy[4:].strip()
        return not _evaluate_policy_recursive(inner_policy, user_attributes)
    
    # Handle parentheses
    if '(' in policy:
        return _evaluate_with_parentheses(policy, user_attributes)
    
    # Handle OR (lower precedence)
    if ' OR ' in policy:
        or_parts = policy.split(' OR ')
        return any(_evaluate_policy_recursive(part.strip(), user_attributes) for part in or_parts)
    
    # Handle AND (higher precedence)
    if ' AND ' in policy:
        and_parts = policy.split(' AND ')
        return all(_evaluate_policy_recursive(part.strip(), user_attributes) for part in and_parts)
    
    return False

def _evaluate_with_parentheses(policy, user_attributes):
    """Handle parentheses in policy evaluation"""
    result = ""
    depth = 0
    i = 0
    
    while i < len(policy):
        char = policy[i]
        
        if char == '(':
            if depth == 0:
                # Start of parentheses group
                start = i + 1
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                # End of parentheses group
                inner_expr = policy[start:i]
                inner_result = _evaluate_policy_recursive(inner_expr, user_attributes)
                result += str(inner_result).lower()  # Convert to 'true'/'false'
            else:
                result += char
        elif depth == 0:
            result += char
        
        i += 1
    
    # Replace 'true'/'false' with actual boolean evaluation
    result = result.replace('true', 'True').replace('false', 'False')
    
    # If we still have logical operators, evaluate recursively
    if any(op in result for op in [' OR ', ' AND ', 'NOT ']):
        # Convert True/False back to policy format for recursive evaluation
        return _evaluate_policy_recursive(result, user_attributes)
    
    # Direct boolean evaluation
    try:
        return eval(result)
    except:
        return False

# ==================== UTILITY FUNCTIONS ====================

def get_user_accessible_data(user):
    """Lấy danh sách dữ liệu mà user có thể truy cập"""
    user_attributes = get_user_attributes_list(user)
    accessible_data = []
    
    for data in ProtectedData.objects.all():
        if evaluate_policy_for_user(data.policy_template.policy_template, user_attributes):
            accessible_data.append(data.id)
    
    return ProtectedData.objects.filter(id__in=accessible_data)

def create_protected_data_with_policy(owner, policy_template, filename=None, 
                                    mime_type=None, file_size=None, description=None):
    """Tạo ProtectedData object với static policy"""
    try:
        protected_data = ProtectedData(
            owner_user=owner,
            policy_template=policy_template,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            description=description
        )
        return protected_data
    except Exception as e:
        print(f"Error creating protected data: {e}")
        return None