# cpabe_service_app/cpabe_handler.py
import os
import uuid
import logging
from django.conf import settings

# Import các thành phần từ các file .py cùng cấp
from .f_cpabe import setup as f_cpabe_setup_util # Đổi tên để tránh nhầm lẫn
from .f_cpabe import gen_secret_key as f_cpabe_gen_key_util # Đổi tên
from .CPABE import CPABE # Lớp bao bọc của bạn

logger = logging.getLogger(__name__)

class CPABEHandler:
    def __init__(self):
        self.config = settings.CPABE_CONFIG
        self.keys_dir = self.config['KEYS_DIR']
        # Tên file được lấy từ settings, f_cpabe.py sẽ sử dụng chúng
        self.pk_filename = self.config['PUBLIC_KEY_FILENAME']
        self.msk_filename = self.config['MASTER_KEY_FILENAME']
        self.pk_file_path = os.path.join(self.keys_dir, self.pk_filename)
        self.msk_file_path = os.path.join(self.keys_dir, self.msk_filename)

        if not os.path.exists(self.keys_dir):
            try:
                os.makedirs(self.keys_dir)
                logger.info(f"Đã tạo thư mục lưu khóa CP-ABE: {self.keys_dir}")
            except OSError as e:
                logger.error(f"Không thể tạo thư mục {self.keys_dir}: {e}")
                raise

        try:
            scheme_name = self.config.get('SCHEME_NAME', "Waters11")
            group_param = self.config.get('PAIRING_GROUP', "SS512")
            uni_size = self.config.get('WATERS11_UNI_SIZE', 100)
            cpabe_wrapper = CPABE(scheme_name, group_param=group_param, uni_size_param=uni_size)
            self.actual_scheme_instance = cpabe_wrapper.scheme_instance
            logger.info(f"Đã khởi tạo CPABE Handler với scheme: {scheme_name}, group: {group_param}, uni_size: {uni_size}")

        except NotImplementedError as e:
            logger.error(f"Lỗi scheme không được hỗ trợ: {e}")
            raise
        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi khởi tạo CPABE instance: {e}")
            raise

    def run_system_setup(self):
        if os.path.exists(self.pk_file_path) and os.path.exists(self.msk_file_path):
            msg = "Hệ thống CP-ABE (PK, MSK) đã được thiết lập trước đó."
            logger.info(msg)
            return True, msg

        try:
            logger.info(f"Đang thực hiện setup hệ thống CP-ABE vào thư mục: {self.keys_dir}")
            f_cpabe_setup_util(
                self.actual_scheme_instance,
                self.keys_dir,
                pk_filename=self.pk_filename,
                msk_filename=self.msk_filename
            )
            if not (os.path.exists(self.pk_file_path) and os.path.exists(self.msk_file_path)):
                error_msg = (f"Lỗi: Hàm setup không tạo ra các file khóa như mong đợi. "
                             f"PK dự kiến: {self.pk_file_path}, MSK dự kiến: {self.msk_file_path}")
                logger.error(error_msg)
                return False, error_msg
            
            msg = "Thiết lập hệ thống CP-ABE thành công."
            logger.info(msg)
            return True, msg
        except Exception as e:
            error_msg = f"Lỗi trong quá trình thiết lập hệ thống CP-ABE: {e}"
            logger.exception(error_msg)
            return False, error_msg

    def get_public_key_content(self):
        if not os.path.exists(self.pk_file_path):
            msg = "Không tìm thấy file Khóa Công Khai. Hệ thống có thể chưa được thiết lập."
            logger.warning(msg)
            return None, msg
        try:
            with open(self.pk_file_path, 'rb') as pk_file:
                return pk_file.read(), None
        except IOError as e:
            error_msg = f"Lỗi I/O khi đọc file Khóa Công Khai {self.pk_file_path}: {e}"
            logger.exception(error_msg)
            return None, error_msg

    def generate_secret_key_content(self, user_attributes_string):
        """
        user_attributes_string: chuỗi thuộc tính đã được định dạng đúng từ model
                                (ví dụ: "ATTR1,ATTR2,ATTR3")
        """
        if not (os.path.exists(self.pk_file_path) and os.path.exists(self.msk_file_path)):
            msg = "Không tìm thấy PK hoặc MSK. Không thể tạo Khóa Bí Mật."
            logger.warning(msg)
            return None, msg

        temp_sk_filename_base = f"{self.config['TEMP_SK_FILENAME_PREFIX']}{uuid.uuid4()}.bin"
        temp_sk_filepath = os.path.join(self.keys_dir, temp_sk_filename_base)

        try:
            logger.info(f"Đang tạo Khóa Bí Mật cho thuộc tính: '{user_attributes_string}' vào file tạm: {temp_sk_filepath}")
            f_cpabe_gen_key_util(
                self.actual_scheme_instance,
                self.pk_file_path,
                self.msk_file_path,
                user_attributes_string,
                temp_sk_filepath
            )

            if os.path.exists(temp_sk_filepath):
                with open(temp_sk_filepath, 'rb') as sk_f:
                    secret_key_content = sk_f.read()
                logger.info(f"Đã tạo và đọc thành công Khóa Bí Mật từ: {temp_sk_filepath}")
                return secret_key_content, None
            else:
                error_msg = f"Lỗi: File Khóa Bí Mật tạm thời {temp_sk_filepath} không được tạo."
                logger.error(error_msg)
                return None, error_msg
        except ValueError as ve:
            error_msg = f"Lỗi giá trị khi tạo Khóa Bí Mật: {ve}"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Lỗi khi tạo Khóa Bí Mật cho thuộc tính '{user_attributes_string}': {e}"
            logger.exception(error_msg)
            return None, error_msg
        finally:
            if os.path.exists(temp_sk_filepath):
                try:
                    os.remove(temp_sk_filepath)
                    logger.info(f"Đã xóa file Khóa Bí Mật tạm thời: {temp_sk_filepath}")
                except OSError as e_del:
                    logger.error(f"Lỗi khi xóa file Khóa Bí Mật tạm thời {temp_sk_filepath}: {e_del}")