from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from backend.models import Attribute, UserAttribute

User = get_user_model()

class Command(BaseCommand):
    help = 'Gán role bác sĩ cho user'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email của user')

    def handle(self, *args, **options):
        email = options['email']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'User với email {email} không tồn tại')
            )
            return

        # Tạo hoặc lấy attribute doctor
        doctor_attr, created = Attribute.objects.get_or_create(
            name='doctor',
            defaults={
                'description': 'Bác sĩ - có quyền upload medical records'
            }
        )
        
        # Gán attribute cho user
        user_attr, created = UserAttribute.objects.get_or_create(
            user=user,
            attribute=doctor_attr
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Đã gán role bác sĩ cho {email}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'User {email} đã có role bác sĩ')
            ) 