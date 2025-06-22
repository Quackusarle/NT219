from django.db import models
import uuid # Vẫn có thể dùng uuid cho ID của bản ghi nếu muốn

class ProtectedEHRTextData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Metadata (Clear Text) ---
    patient_id_on_rs = models.CharField(
        max_length=100,
        db_index=True,
        verbose_name="Mã Bệnh Nhân (trên RS)"
    )
    created_by_ac_user_id = models.IntegerField(
        db_index=True,
        verbose_name="Người Tạo (ID từ Auth Center)"
    )
    description = models.CharField( # Có thể là CharField nếu mô tả ngắn
        max_length=500, # Hoặc TextField nếu mô tả có thể dài
        blank=True, null=True,
        verbose_name="Mô Tả Chung"
    )
    data_type = models.CharField(
        max_length=100,
        blank=True, null=True,
        verbose_name="Loại Dữ Liệu",
        help_text="Ví dụ: CONSULTATION_NOTE, LAB_RESULT_SUMMARY"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày Tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày Cập Nhật")

    # --- Thông tin về chính sách CP-ABE đã áp dụng ---
    cpabe_policy_applied = models.TextField(verbose_name="Chính sách CP-ABE đã áp dụng cho KEK")

    # --- Các thành phần đã được mã hóa phía Client ---
    # KEK (Key Encryption Key - khóa AES) đã được mã hóa bằng CP-ABE, sau đó encode Base64
    encrypted_kek_b64 = models.TextField(verbose_name="KEK đã mã hóa CP-ABE (Base64)")

    # IV (Initialization Vector) của AES-GCM, đã được encode Base64
    aes_iv_b64 = models.CharField(max_length=24, verbose_name="AES IV (Base64)") # IV của AES-GCM thường là 12 bytes, Base64 sẽ dài hơn chút

    # Nội dung chính đã được mã hóa bằng AES-GCM (sử dụng KEK), sau đó encode Base64
    encrypted_main_content_b64 = models.TextField(verbose_name="Nội dung chính đã mã hóa AES (Base64)")


    # (Tùy chọn) Metadata cho việc kiểm soát truy cập API (ABAC trên RS)
    # api_access_abac_policy = models.JSONField(default=dict, blank=True, verbose_name="Chính sách ABAC truy cập API")

    class Meta:
        verbose_name = "Dữ Liệu EHR Văn Bản Đã Mã Hóa"
        verbose_name_plural = "Các Dữ Liệu EHR Văn Bản Đã Mã Hóa"
        ordering = ['-created_at']

    def __str__(self):
        return f"EHR Text Entry for Patient {self.patient_id_on_rs} (Type: {self.data_type or 'N/A'}) by UserACID {self.created_by_ac_user_id} on {self.created_at.strftime('%Y-%m-%d')}"