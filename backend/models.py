from django.db import models

# Create your models here.

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class CustomUserManager(BaseUserManager):  
    def create_user(self, email, password=None, **extra_fields):  
        if not email:  
            raise ValueError("The Email field must be set")  
        email = self.normalize_email(email)  
        user = self.model(email=email, **extra_fields)  
        user.set_password(password)  
        user.save(using=self._db)  
        return user  

    def create_superuser(self, email, password=None, **extra_fields):  
        extra_fields.setdefault('is_staff', True)  
        extra_fields.setdefault('is_superuser', True)  
        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    objects = CustomUserManager()
    
    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        return self.first_name


class Attribute(models.Model):
    """
    Model lưu trữ các thuộc tính có thể có (lá trong cây chính sách).
    Ví dụ: "Family members", "Personal doctor", "Hospital 1", "Researcher", "M.D."
    """
    name = models.CharField(max_length=255, unique=True, help_text="Tên thuộc tính, ví dụ: 'Researcher'")
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Thuộc tính"
        verbose_name_plural = "Các Thuộc tính"

class UserAttribute(models.Model):
    """
    Bảng trung gian liên kết Người dùng (từ django.contrib.auth hoặc custom user model)
    với các Thuộc tính họ sở hữu.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, # Sử dụng User model được cấu hình trong Django
        on_delete=models.CASCADE,
        related_name="attributes_possessed"
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.CASCADE,
        related_name="users_with_attribute"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'attribute') # Đảm bảo mỗi cặp user-attribute là duy nhất
        verbose_name = "Thuộc tính Người dùng"
        verbose_name_plural = "Các Thuộc tính Người dùng"

    def __str__(self):
        # Giả sử User model của bạn có trường 'username'
        # Nếu bạn dùng custom user model không có 'username', hãy điều chỉnh cho phù hợp
        username_display = getattr(self.user, self.user.USERNAME_FIELD, self.user.pk)
        return f"{username_display} - {self.attribute.name}"

class AccessPolicy(models.Model):
    """
    Model lưu trữ định nghĩa của các chính sách truy cập.
    """
    name = models.CharField(max_length=255, unique=True, help_text="Tên gợi nhớ cho chính sách")
    policy_definition = models.TextField(
        help_text="Chuỗi định nghĩa chính sách theo cú pháp của thư viện CP-ABE"
    )
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Chính sách Truy cập"
        verbose_name_plural = "Các Chính sách Truy cập"

class ProtectedData(models.Model):
    """
    Model lưu trữ dữ liệu đã được mã hóa hoàn toàn ở phía client.
    Backend chỉ đóng vai trò lưu trữ và cung cấp các blob này.
    Việc mã hóa khóa AES bằng CP-ABE và mã hóa nội dung bằng AES-GCM
    đều được thực hiện bởi client (JavaScript).
    """
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_data",
        help_text="Người dùng đã tải lên và mã hóa dữ liệu này"
    )
    policy = models.ForeignKey(
        AccessPolicy, # Backend vẫn cần biết chính sách nào client đã sử dụng
        on_delete=models.PROTECT, # Ngăn xóa chính sách nếu còn dữ liệu liên quan
        related_name="client_encrypted_data_items", # Đổi related_name cho rõ ràng hơn
        help_text="Chính sách truy cập mà client đã sử dụng để mã hóa khóa AES bằng CP-ABE"
    )

    # Đây là ciphertext của khóa AES, được mã hóa bằng CP-ABE ở client.
    # Client sẽ sử dụng User Secret Key (SK) của họ để giải mã blob này
    # và lấy lại khóa AES gốc.
    # Tên trường này ngụ ý rằng đây là kết quả cuối cùng của việc ABE mã hóa khóa AES.
    abe_encrypted_aes_key_blob = models.BinaryField(
        help_text="Khóa AES (đã được client mã hóa bằng CP-ABE theo chính sách đã chọn)"
    )

    # Các thành phần cần thiết để client giải mã nội dung file bằng khóa AES (sau khi đã giải mã ABE ở trên)
    aes_iv_for_content = models.BinaryField(
        help_text="IV được client sử dụng cho mã hóa AES-GCM của nội dung file"
    )
    # aes_auth_tag_for_content có thể không cần thiết nếu thư viện AES-GCM của client
    # gắn tag vào cuối ciphertext (phổ biến). Nếu client gửi tag riêng thì cần trường này.
    # Để đơn giản, giả sử tag được gắn vào encrypted_content_blob.
    # Nếu client gửi tag riêng:
    # aes_auth_tag_for_content = models.BinaryField(
    # help_text="Authentication Tag được client tạo ra cho mã hóa AES-GCM của nội dung file"
    # )

    encrypted_content_blob = models.BinaryField(
        help_text="Nội dung file đã được client mã hóa bằng AES-GCM (có thể đã bao gồm auth tag)"
    )

    # Metadata
    filename = models.CharField(max_length=255, null=True, blank=True)
    mime_type = models.CharField(max_length=100, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Client Encrypted Data ID: {self.id} (Policy: {self.policy.name})"

    class Meta:
        verbose_name = "Dữ liệu Mã hóa Phía Client"
        verbose_name_plural = "Các Dữ liệu Mã hóa Phía Client"
        ordering = ['-uploaded_at']