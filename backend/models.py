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
    """
    Custom User Manager để quản lý việc tạo user với email thay vì username
    """
    def create_user(self, email, password=None, **extra_fields):
        """Tạo user thường"""
        if not email:
            raise ValueError("Email là bắt buộc")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Tạo superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser phải có is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser phải có is_superuser=True.')
            
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User Model với patient_id tự động
    
    Mỗi user khi đăng ký sẽ:
    1. Có email làm username
    2. Tự động được gán patient_id unique
    3. Tự động có attribute 'patient'
    """
    # Thông tin cơ bản
    email = models.EmailField(
        unique=True,
        help_text="Email đăng nhập, phải unique"
    )
    first_name = models.CharField(
        max_length=30, 
        blank=True,
        help_text="Tên"
    )
    last_name = models.CharField(
        max_length=30, 
        blank=True,
        help_text="Họ"
    )
    
    # Patient ID - Quan trọng cho CP-ABE
    patient_id = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        db_index=True,
        help_text="ID bệnh nhân duy nhất, tự động tạo khi đăng ký"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Permissions
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    # Django settings
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()
    
    def save(self, *args, **kwargs):
        """Override save để tự động tạo patient_id"""
        if not self.patient_id:
            self.patient_id = self.generate_patient_id()
        super().save(*args, **kwargs)
    
    def generate_patient_id(self):
        """
        Tạo patient ID unique 100% bằng UUID
        
        Chiến lược: Dùng UUID4 và lấy 10 ký tự đầu
        - UUID4 có 32 ký tự hex → 2^128 combinations  
        - Lấy 10 ký tự đầu → vẫn có 16^10 = 2^40 combinations
        - Xác suất trùng: 1/(2^40) ≈ 1/1,000,000,000,000
        
        Format: P + 10 ký tự UUID (chữ hoa + số)
        Ví dụ: PA1B2C3D4E, P9F8E7D6C5
        """
        import uuid
        
        while True:
            # Tạo UUID4 và lấy 10 ký tự đầu  
            uuid_str = str(uuid.uuid4()).replace('-', '').upper()[:10]
            patient_id = f"P{uuid_str}"
            
            # Kiểm tra unique (chỉ để chắc chắn, thực tế rất hiếm trùng)
            if not User.objects.filter(patient_id=patient_id).exists():
                return patient_id
            
            # Nếu trùng (xác suất 1/trillion), tạo UUID mới
    
    def __str__(self):
        return f"{self.email} ({self.patient_id})"
    
    def get_full_name(self):
        """Trả về họ tên đầy đủ"""
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    def get_short_name(self):
        """Trả về tên ngắn"""
        return self.first_name or self.email.split('@')[0]

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"


# ==================== ATTRIBUTE SYSTEM ====================

class Attribute(models.Model):
    """
    Model lưu trữ các loại thuộc tính có thể có trong hệ thống CP-ABE
    
    Ví dụ:
    - patient: thuộc tính mặc định cho mọi user
    - doctor: thuộc tính cho bác sĩ
    - family_member: thuộc tính cho thành viên gia đình (có patient_id)
    - nurse: thuộc tính cho y tá
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Tên thuộc tính, ví dụ: 'doctor', 'family_member'"
    )
    description = models.TextField(
        null=True, blank=True,
        help_text="Mô tả chi tiết về thuộc tính này"
    )
    supports_patient_id = models.BooleanField(
        default=False,
        help_text="Có hỗ trợ patient_id không? (patient=True, family_members=True)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Thuộc tính"
        verbose_name_plural = "Thuộc tính"
        ordering = ['name']


class UserAttribute(models.Model):
    """
    Bảng trung gian lưu trữ attributes của từng user
    
    Ví dụ:
    - User A có attribute 'patient:P1234567890' (patient_id của chính họ)
    - User B có attribute 'doctor' (không có patient_id)  
    - User C có attribute 'family_members:P1234567890' (thành viên gia đình của bệnh nhân P1234567890)
    """
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
    patient_id = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="Patient ID cụ thể (dành cho patient và family_members)"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'attribute', 'patient_id')
        verbose_name = "Thuộc tính người dùng"
        verbose_name_plural = "Thuộc tính người dùng"
        indexes = [
            models.Index(fields=['user', 'attribute']),
            models.Index(fields=['patient_id']),
            models.Index(fields=['attribute', 'patient_id']),
        ]

    def clean(self):
        """Validation logic"""
        # Rule 1: Chỉ những attribute có supports_patient_id=True mới được có patient_id
        if self.patient_id and not self.attribute.supports_patient_id:
            raise ValidationError(
                f"Attribute '{self.attribute.name}' không được có patient_id"
            )
        
        # Rule 2: family_members bắt buộc phải có patient_id
        if (self.attribute.supports_patient_id and 
            self.attribute.name == 'family_members' and 
            not self.patient_id):
            raise ValidationError(
                "Attribute 'family_members' bắt buộc phải có patient_id"
            )
        
        # Rule 3: patient bắt buộc phải có patient_id của chính mình
        if (self.attribute.supports_patient_id and 
            self.attribute.name == 'patient'):
            if not self.patient_id:
                raise ValidationError(
                    "Attribute 'patient' bắt buộc phải có patient_id"
                )
            # Patient phải có patient_id của chính mình
            if (hasattr(self.user, 'patient_id') and 
                self.patient_id != self.user.patient_id):
                raise ValidationError(
                    f"Attribute 'patient' chỉ có thể có patient_id của chính user đó"
                )
        
        # Rule 4: patient_id phải tồn tại trong database
        if self.patient_id:
            if not User.objects.filter(patient_id=self.patient_id).exists():
                raise ValidationError(
                    f"Không tìm thấy bệnh nhân với ID '{self.patient_id}'"
                )
        
        # Rule 5: Chỉ family_members không được tự trỏ đến chính mình
        if (self.attribute.name == 'family_members' and 
            self.patient_id and 
            hasattr(self.user, 'patient_id') and 
            self.patient_id == self.user.patient_id):
            raise ValidationError(
                "Không thể tự làm thành viên gia đình của chính mình"
            )

    def save(self, *args, **kwargs):
        """Override save để chạy validation"""
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        username = self.user.email
        if self.patient_id and self.attribute.supports_patient_id:
            return f"{username} - {self.attribute.name}:{self.patient_id}"
        return f"{username} - {self.attribute.name}"
    
    @property
    def full_attribute_name(self):
        """
        Trả về tên attribute đầy đủ cho CP-ABE
        
        Returns:
        - 'doctor' (nếu là attribute đơn giản)
        - 'family_member:P1234567890' (nếu có patient_id)
        """
        if self.patient_id and self.attribute.supports_patient_id:
            return f"{self.attribute.name}:{self.patient_id}"
        return self.attribute.name


# ==================== POLICY SYSTEM ====================

class AccessPolicy(models.Model):
    """
    Model lưu trữ các template chính sách truy cập CP-ABE
    
    Thay vì lưu policy cứng như 'family_member:P1234567890',
    ta lưu template như 'family_member:{{PATIENT_ID}}' và render động.
    
    Ví dụ:
    - Template: 'family_member:{{PATIENT_ID}}'
    - Render với PATIENT_ID='P1234567890' 
    - Kết quả: 'family_member:P1234567890'
    """
    POLICY_TYPES = [
        ('static', 'Chính sách tĩnh - không cần patient_id'),
        ('patient_specific', 'Chính sách theo bệnh nhân - cần patient_id'),
        ('dynamic', 'Chính sách động - có thể có nhiều placeholder'),
    ]
    
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Tên gợi nhớ cho policy template"
    )
    policy_template = models.TextField(
        help_text="Template chính sách với placeholder {{PATIENT_ID}}, {{HOSPITAL_ID}}, etc."
    )
    policy_type = models.CharField(
        max_length=20,
        choices=POLICY_TYPES,
        default='static',
        help_text="Loại chính sách"
    )
    description = models.TextField(
        null=True, blank=True,
        help_text="Mô tả chi tiết về chính sách này"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def render_policy(self, patient_id=None, **context):
        """
        Render policy template với context cụ thể
        
        Args:
            patient_id: ID của bệnh nhân
            **context: Các placeholder khác (hospital_id, dept_id, etc.)
            
        Returns:
            str: Policy đã được render
            
        Example:
            policy.render_policy(patient_id='P1234567890')
            # 'family_member:{{PATIENT_ID}}' -> 'family_member:P1234567890'
        """
        policy = self.policy_template
        
        # Thay thế PATIENT_ID
        if patient_id and self.policy_type in ['patient_specific', 'dynamic']:
            policy = policy.replace('{{PATIENT_ID}}', str(patient_id))
        
        # Thay thế các placeholder khác
        for key, value in context.items():
            placeholder = f'{{{{{key.upper()}}}}}'
            policy = policy.replace(placeholder, str(value))
        
        return policy
    
    def is_applicable_for_patient(self, patient_id):
        """
        Kiểm tra policy có áp dụng được cho patient không
        
        Args:
            patient_id: ID của bệnh nhân
            
        Returns:
            bool: True nếu có thể áp dụng
        """
        if self.policy_type == 'static':
            return True
        elif self.policy_type in ['patient_specific', 'dynamic']:
            return patient_id is not None
        return False
    
    def get_required_placeholders(self):
        """
        Lấy danh sách các placeholder cần thiết trong template
        
        Returns:
            list: Danh sách placeholder như ['PATIENT_ID', 'HOSPITAL_ID']
        """
        import re
        placeholders = re.findall(r'\{\{(\w+)\}\}', self.policy_template)
        return list(set(placeholders))

    def __str__(self):
        return f"{self.name} ({self.policy_type})"

    class Meta:
        verbose_name = "Chính sách truy cập"
        verbose_name_plural = "Chính sách truy cập"
        ordering = ['name']


class ProtectedData(models.Model):
    """
    Model lưu trữ dữ liệu đã được mã hóa bằng CP-ABE
    
    Workflow:
    1. Client chọn policy template và patient_id
    2. Server render policy cụ thể
    3. Client mã hóa AES key bằng CP-ABE với policy đã render
    4. Client mã hóa data bằng AES
    5. Server lưu trữ cả encrypted AES key và encrypted data
    """
    # Metadata
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="owned_data",
        help_text="User đã upload và mã hóa dữ liệu này"
    )
    
    # Policy information
    policy_template = models.ForeignKey(
        AccessPolicy,
        on_delete=models.PROTECT,
        related_name="protected_data_items",
        help_text="Template chính sách được sử dụng"
    )
    target_patient_id = models.CharField(
        max_length=50,
        null=True, blank=True,
        help_text="Patient ID mà dữ liệu này thuộc về (cho patient-specific policies)"
    )
    rendered_policy = models.TextField(
        help_text="Policy đã được render với patient_id cụ thể (cache để tối ưu)"
    )
    
    # Encrypted data
    abe_encrypted_aes_key_blob = models.BinaryField(
        help_text="AES key đã được mã hóa bằng CP-ABE (client thực hiện)"
    )
    aes_iv_for_content = models.BinaryField(
        help_text="IV được sử dụng cho AES-GCM encryption của nội dung"
    )
    encrypted_content_blob = models.BinaryField(
        help_text="Nội dung file đã được mã hóa bằng AES-GCM (client thực hiện)"
    )
    
    # File metadata
    filename = models.CharField(
        max_length=255,
        null=True, blank=True,
        help_text="Tên file gốc"
    )
    mime_type = models.CharField(
        max_length=100,
        null=True, blank=True,
        help_text="MIME type của file"
    )
    file_size = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Kích thước file gốc (bytes)"
    )
    description = models.TextField(
        null=True, blank=True,
        help_text="Mô tả về file này"
    )
    
    # Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        """Override save để tự động render policy"""
        if self.policy_template and not self.rendered_policy:
            self.rendered_policy = self.policy_template.render_policy(
                patient_id=self.target_patient_id
            )
        super().save(*args, **kwargs)
    
    def can_user_access(self, user):
        """
        Kiểm tra user có thể truy cập dữ liệu này không
        (Dựa trên attributes của user và policy đã render)
        
        Args:
            user: User object
            
        Returns:
            bool: True nếu có quyền truy cập
        """
        # Import ở đây để tránh circular import
        from .abe_utils import evaluate_policy_for_user
        
        user_attributes = [
            ua.full_attribute_name 
            for ua in user.attributes_possessed.select_related('attribute')
        ]
        
        return evaluate_policy_for_user(self.rendered_policy, user_attributes)
    
    def get_file_info(self):
        """
        Trả về thông tin file để hiển thị
        
        Returns:
            dict: Thông tin file
        """
        return {
            'filename': self.filename,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'uploaded_at': self.uploaded_at,
            'policy': self.rendered_policy,
            'owner': self.owner_user.get_full_name() if self.owner_user else 'Unknown'
        }

    def __str__(self):
        return f"Protected Data: {self.filename or f'ID-{self.id}'} (Policy: {self.policy_template.name})"

    class Meta:
        verbose_name = "Dữ liệu được bảo vệ"
        verbose_name_plural = "Dữ liệu được bảo vệ"
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['target_patient_id']),
            models.Index(fields=['policy_template', 'target_patient_id']),
            models.Index(fields=['owner_user', 'uploaded_at']),
        ]


# ==================== SIGNALS ====================

@receiver(post_save, sender=User)
def create_default_patient_attribute(sender, instance, created, **kwargs):
    """
    Signal tự động gán attribute 'patient' cho user mới đăng ký
    
    Chạy sau khi User được tạo thành công để tránh database lock.
    Sử dụng transaction.on_commit để đảm bảo chạy sau khi transaction hoàn tất.
    """
    if created:
        # Chạy trong transaction riêng để tránh deadlock
        transaction.on_commit(lambda: _create_patient_attribute(instance))


def _create_patient_attribute(user_instance):
    """
    Helper function để tạo patient attribute
    
    Args:
        user_instance: User object vừa được tạo
    """
    try:
        # Lấy hoặc tạo attribute 'patient' với supports_patient_id=True
        patient_attr, created = Attribute.objects.get_or_create(
            name='patient',
            defaults={
                'description': 'Bệnh nhân - có quyền truy cập dữ liệu bệnh nhân cụ thể',
                'supports_patient_id': True
            }
        )
        
        # Gán attribute 'patient' cho user với patient_id của chính họ
        # Ví dụ: user có patient_id='P1234567890' sẽ có attribute 'patient:P1234567890'
        UserAttribute.objects.get_or_create(
            user=user_instance,
            attribute=patient_attr,
            patient_id=user_instance.patient_id  # Quan trọng: dùng patient_id của chính user
        )
        
        logger.info(f"Created patient attribute for user {user_instance.email} with patient_id {user_instance.patient_id}")
        
    except Exception as e:
        logger.error(f"Error creating patient attribute for user {user_instance.id}: {e}")