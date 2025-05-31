import base64
import os
from pathlib import Path
import pickle
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from charm.toolbox.pairinggroup import PairingGroup, GT
from charm.schemes.abenc.ac17 import AC17CPABE


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