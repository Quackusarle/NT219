import os
import pickle
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from backend.abe_utils import (
    get_charm_group,
    get_waters11_scheme,
    PK_FILE_PATH,
    MSK_FILE_PATH,
    ABE_PARAMS_DIR,
    ABE_SECURE_KEYS_DIR
)

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

class Command(BaseCommand):
    help = ('Sets up the CP-ABE Waters11 system: generates and saves '
            'Public Parameters (PK) and Master Secret Key (MSK) using Charm-Crypto.')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing CP-ABE Waters11 setup using Charm-Crypto..."))

        try:
            group = get_charm_group()
            waters11_scheme = get_waters11_scheme()

            if group is None or waters11_scheme is None:
                raise CommandError("Charm-Crypto group or Waters11 scheme not initialized.")

            self.stdout.write("Charm-Crypto group and Waters11 scheme retrieved.")
            # Sửa lỗi hiển thị groupType:
            self.stdout.write(f"Using pairing group: {group.groupType()}")
            self.stdout.write(f"Waters11 scheme universe size: {waters11_scheme.uni_size}")

            self.stdout.write("Generating Public Parameters (PK) and Master Secret Key (MSK)...")
            pk_charm, msk_charm = waters11_scheme.setup() # Đây là các dict chứa pairing.Element
            self.stdout.write(self.style.SUCCESS("PK and MSK generated successfully by Charm-Crypto."))

            os.makedirs(ABE_PARAMS_DIR, exist_ok=True)
            os.makedirs(ABE_SECURE_KEYS_DIR, exist_ok=True)
            self.stdout.write(f"Ensured directory exists: {ABE_PARAMS_DIR}")
            self.stdout.write(f"Ensured directory exists: {ABE_SECURE_KEYS_DIR}")

            # Serialize pk_charm và msk_charm trước khi pickle
            self.stdout.write("Serializing PK and MSK components...")
            serialized_pk = serialize_charm_object(group, pk_charm)
            serialized_msk = serialize_charm_object(group, msk_charm)
            self.stdout.write(self.style.SUCCESS("PK and MSK components serialized."))

            try:
                with open(PK_FILE_PATH, 'wb') as f_pk:
                    pickle.dump(serialized_pk, f_pk) # Lưu dictionary đã serialize các phần tử
                self.stdout.write(self.style.SUCCESS(f"Serialized Public Parameters (PK) saved to: {PK_FILE_PATH}"))
            except Exception as e:
                raise CommandError(f"Error saving serialized PK: {e}")

            try:
                with open(MSK_FILE_PATH, 'wb') as f_msk:
                    pickle.dump(serialized_msk, f_msk) # Lưu dictionary đã serialize các phần tử
                if os.name == 'posix':
                    os.chmod(MSK_FILE_PATH, 0o600)
                    self.stdout.write(self.style.SUCCESS(f"Permissions for MSK file set to 600."))
                else:
                    self.stdout.write(self.style.WARNING(f"Cannot set POSIX permissions for MSK file on {os.name}. Secure manually."))
                self.stdout.write(self.style.SUCCESS(f"Serialized Master Secret Key (MSK) saved to: {MSK_FILE_PATH}"))
                self.stdout.write(self.style.WARNING("IMPORTANT: Add MSK path to .gitignore."))
            except Exception as e:
                raise CommandError(f"Error saving serialized MSK: {e}")

            self.stdout.write(self.style.SUCCESS("CP-ABE Waters11 system setup command finished successfully."))

        except ImproperlyConfigured as e:
            raise CommandError(f"Configuration error: {e}")
        except Exception as e:
            import traceback
            self.stderr.write(self.style.ERROR(f"An unexpected error occurred: {e}"))
            self.stderr.write(traceback.format_exc())
            raise CommandError(f"Setup failed due to an unexpected error: {e}")