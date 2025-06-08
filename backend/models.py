import uuid
import secrets
import string
import logging
from django.db import models, transaction
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ==================== USER MANAGEMENT ====================

class CustomUserManager(BaseUserManager):
    """Custom User Manager để quản lý việc tạo user với email thay vì username"""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email là bắt buộc")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser phải có is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser phải có is_superuser=True.')
            
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """Custom User Model đơn giản cho Waters11 - chỉ static attributes"""
    email = models.EmailField(unique=True, help_text="Email đăng nhập")
    first_name = models.CharField(max_length=30, blank=True, help_text="Tên")
    last_name = models.CharField(max_length=30, blank=True, help_text="Họ")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Permissions
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        return self.first_name or self.email.split('@')[0]

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

# ==================== ATTRIBUTE SYSTEM ====================

class Attribute(models.Model):
    """Model lưu trữ các static attributes cho CP-ABE Waters11"""
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Tên thuộc tính static, ví dụ: 'doctor', 'nurse'"
    )
    description = models.TextField(
        null=True, blank=True,
        help_text="Mô tả chi tiết về thuộc tính này"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Thuộc tính"
        verbose_name_plural = "Thuộc tính"
        ordering = ['name']

class UserAttribute(models.Model):
    """Bảng trung gian lưu trữ static attributes của từng user"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attributes_possessed",
        help_text="User sở hữu attribute này"
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name="users_with_attribute",
        help_text="Loại attribute"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'attribute')
        verbose_name = "Thuộc tính người dùng"
        verbose_name_plural = "Thuộc tính người dùng"
        indexes = [
            models.Index(fields=['user', 'attribute']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.attribute.name}"

# ==================== POLICY SYSTEM ====================

class AccessPolicy(models.Model):
    """Model lưu trữ các static access policies cho Waters11"""
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Tên gợi nhớ cho policy"
    )
    policy_template = models.TextField(
        help_text="Static policy string, ví dụ: 'doctor OR (hospital_1 AND nurse)'"
    )
    description = models.TextField(
        null=True, blank=True,
        help_text="Mô tả chi tiết về chính sách này"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Chính sách truy cập"
        verbose_name_plural = "Chính sách truy cập"
        ordering = ['name']

# ==================== MEDICAL DATA ====================

def generate_case_id():
    """Tạo mã định danh hồ sơ bệnh án"""
    return f"CASE-{uuid.uuid4().hex[:8].upper()}"

class MedicalData(models.Model):
    """Model lưu trữ dữ liệu y tế đã được mã hóa bằng AES và CP-ABE Waters11"""
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="owned_medical_data",
        help_text="User đã tạo dữ liệu y tế này"
    )
    
    # THÊM MỚI: Patient ID không mã hóa để phân biệt các hồ sơ
    patient_id = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="Mã số bệnh nhân (không mã hóa) để phân biệt các hồ sơ"
    )
    
    # Patient information - encrypted data (dữ liệu đã mã hóa)
    patient_id_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Mã số bệnh nhân đã mã hóa"
    )
    patient_name_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Họ tên bệnh nhân đã mã hóa"
    )
    patient_age_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Tuổi bệnh nhân đã mã hóa"
    )
    patient_gender_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Giới tính bệnh nhân đã mã hóa"
    )
    patient_phone_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Số điện thoại bệnh nhân đã mã hóa"
    )

    # AES key và IV cho thông tin bệnh nhân
    patient_info_aes_key_blob = models.BinaryField(
        help_text="AES key cho thông tin bệnh nhân, đã mã hóa bằng CP-ABE Waters11"
    )
    patient_info_aes_iv_blob = models.BinaryField( 
        help_text="IV cho AES-GCM encryption thông tin bệnh nhân"
    )
    
    # Medical record - encrypted data (dữ liệu đã mã hóa)
    chief_complaint_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Lý do khám đã mã hóa"
    )
    past_medical_history_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Tiền sử bệnh đã mã hóa"
    )
    diagnosis_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Chẩn đoán đã mã hóa"
    )
    status_blob = models.BinaryField(
        null=True, blank=True,
        help_text="Tình trạng hiện tại đã mã hóa"
    )
    
    # AES key và IV cho hồ sơ y tế
    medical_record_aes_key_blob = models.BinaryField(
        help_text="AES key cho hồ sơ y tế, đã mã hóa bằng CP-ABE Waters11"
    )
    medical_record_aes_iv_blob = models.BinaryField(
        help_text="IV cho AES-GCM encryption hồ sơ y tế"
    )

    # Metadata không mã hóa
    case_id = models.CharField(
        max_length=100,
        unique=True,
        default=generate_case_id,  # SỬA: Dùng function thay vì lambda
        help_text="Mã định danh hồ sơ bệnh án"
    )
    created_date = models.DateField(
        auto_now_add=True,
        help_text="Ngày tạo hồ sơ"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.patient_id:
            return f"Medical Data {self.case_id} - Patient {self.patient_id}"
        return f"Medical Data {self.case_id}"

    class Meta:
        verbose_name = "Dữ liệu y tế"
        verbose_name_plural = "Dữ liệu y tế"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner_user', 'created_at']),
            models.Index(fields=['case_id']),
        ]