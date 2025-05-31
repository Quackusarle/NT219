from django.apps import AppConfig

class BackendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend' # Tên app của bạn

    def ready(self):
        from . import abe_utils
        try:
            abe_utils.init_charm_settings()
            print("Charm-Crypto initialized successfully via AppConfig.")
        except Exception as e:
            print(f"Error initializing Charm-Crypto: {e}")
