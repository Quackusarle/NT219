# cpabe_service_app/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model # Cách tốt hơn để lấy User model
from .models import Attribute, UserProfile

User = get_user_model() # Lấy User model hiện tại của project

# Inline cho UserProfile để hiển thị trong trang User của Django Admin
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False # Không cho phép xóa UserProfile từ trang User (nếu xóa User thì UserProfile sẽ tự xóa theo cascade)
    verbose_name_plural = 'Hồ sơ CP-ABE và Thuộc tính'
    # filter_horizontal làm cho việc chọn nhiều thuộc tính dễ dàng hơn
    filter_horizontal = ('attributes',)
    # (Tùy chọn) Nếu bạn muốn hiển thị các trường của UserProfile trực tiếp
    # fields = ('some_other_field_in_userprofile', 'attributes')

# Mở rộng UserAdmin mặc định để bao gồm UserProfileInline
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    # Bạn có thể thêm các tùy chỉnh khác cho UserAdmin ở đây nếu muốn
    # list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_cpabe_attributes_count')
    #
    # def get_cpabe_attributes_count(self, obj):
    #     try:
    #         return obj.cpabe_profile.attributes.count()
    #     except UserProfile.DoesNotExist:
    #         return 0
    # get_cpabe_attributes_count.short_description = 'Số thuộc tính CP-ABE'

# Đăng ký lại User model với CustomUserAdmin
# Cần unregister UserAdmin mặc định trước nếu nó đã được đăng ký
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass # Bỏ qua nếu User chưa được đăng ký (ví dụ khi chạy test lần đầu)
admin.site.register(User, CustomUserAdmin)


# Tùy chỉnh cách hiển thị Attribute trong Django Admin
@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    # Các trường hiển thị trong danh sách Attribute
    list_display = ('name',)
    # Các trường có thể tìm kiếm
    search_fields = ('name',)
    # (Tùy chọn) Các trường có thể lọc
    # list_filter = (...)
    # (Tùy chọn) Thứ tự sắp xếp mặc định
    ordering = ('name',) 
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
     list_display = ('user', 'get_assigned_attributes')
     filter_horizontal = ('attributes',)

     def get_assigned_attributes(self, obj):
         return ", ".join([attr.name for attr in obj.attributes.all()])
     get_assigned_attributes.short_description = 'Thuộc tính đã gán (IDs)'