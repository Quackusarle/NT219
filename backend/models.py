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

class ProtectedData(models.Model):
    """Model lưu trữ dữ liệu đã được mã hóa bằng CP-ABE Waters11"""
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="owned_data",
        help_text="User đã upload và mã hóa dữ liệu này"
    )
    
    policy_template = models.ForeignKey(
        AccessPolicy,
        on_delete=models.PROTECT,
        related_name="protected_data_items",
        help_text="Chính sách được sử dụng"
    )
    
    # Encrypted data
    abe_encrypted_aes_key_blob = models.BinaryField(
        help_text="AES key đã được mã hóa bằng CP-ABE Waters11"
    )
    aes_iv_for_content = models.BinaryField(
        help_text="IV được sử dụng cho AES-GCM encryption"
    )
    encrypted_content_blob = models.BinaryField(
        help_text="Nội dung file đã được mã hóa bằng AES-GCM"
    )
    
    # File metadata
    filename = models.CharField(max_length=255, null=True, blank=True)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_user_access(self, user):
        """Kiểm tra user có thể truy cập dữ liệu này không"""
        from .abe_utils import evaluate_policy_for_user
        
        user_attributes = [
            ua.attribute.name 
            for ua in user.attributes_possessed.select_related('attribute')
        ]
        
        return evaluate_policy_for_user(self.policy_template.policy_template, user_attributes)

    class Meta:
        verbose_name = "Dữ liệu được bảo vệ"
        verbose_name_plural = "Dữ liệu được bảo vệ"
        indexes = [
            models.Index(fields=['owner_user', 'uploaded_at']),
            models.Index(fields=['policy_template']),
        ]