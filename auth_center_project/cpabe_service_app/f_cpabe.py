import os
from charm.core.engine.util import objectToBytes, bytesToObject

def _save_bytes_to_file(data_bytes, filename):
    with open(filename, 'wb') as file:
        file.write(data_bytes)

def _load_bytes_from_file(filename):
    with open(filename, 'rb') as file:
        return file.read()

def setup(actual_waters11_scheme_instance, output_directory_path, pk_filename="public_key.bin", msk_filename="master_key.bin"):
    if not os.path.exists(output_directory_path):
        os.makedirs(output_directory_path)
    public_key_dict, master_key_dict = actual_waters11_scheme_instance.setup()
    serialized_public_key = objectToBytes(public_key_dict, actual_waters11_scheme_instance.group)
    serialized_master_key = objectToBytes(master_key_dict, actual_waters11_scheme_instance.group)
    full_pk_path = os.path.join(output_directory_path, pk_filename)
    full_msk_path = os.path.join(output_directory_path, msk_filename)
    _save_bytes_to_file(serialized_public_key, full_pk_path)
    _save_bytes_to_file(serialized_master_key, full_msk_path)
    return full_pk_path, full_msk_path


def gen_secret_key(actual_waters11_scheme_instance, public_key_file_path, master_key_file_path,
                   user_attributes_string, output_sk_file_path):
    pk_dict = bytesToObject(_load_bytes_from_file(public_key_file_path), actual_waters11_scheme_instance.group)
    msk_dict = bytesToObject(_load_bytes_from_file(master_key_file_path), actual_waters11_scheme_instance.group)
    attr_list = [attr.strip().upper() for attr in user_attributes_string.split(',') if attr.strip()] # Chuẩn hóa và upper
    if not attr_list:
        raise ValueError("Attribute list cannot be empty for key generation.")
    user_secret_key_dict = actual_waters11_scheme_instance.keygen(pk_dict, msk_dict, attr_list)
    serialized_user_secret_key = objectToBytes(user_secret_key_dict, actual_waters11_scheme_instance.group)
    _save_bytes_to_file(serialized_user_secret_key, output_sk_file_path)
    return output_sk_file_path
