from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Attribute, UserAttribute, MedicalData


class UserAttributeInline(admin.TabularInline):
    """Inline để hiển thị attributes của user trong User admin"""
    model = UserAttribute
    extra = 1
    autocomplete_fields = ('attribute',)
    fields = ('attribute', 'assigned_at')
    readonly_fields = ('assigned_at',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'get_attributes_count', 'is_active', 'is_staff', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'last_login_ip')
    inlines = [UserAttributeInline]
    
    def get_attributes_count(self, obj):
        """Hiển thị số lượng attributes của user"""
        return obj.attributes_possessed.count()
    get_attributes_count.short_description = 'Attributes Count'
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'created_at', 'updated_at')}),
        (_('Additional info'), {'fields': ('last_login_ip',)}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_users_count', 'description', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)
    ordering = ('name',)
    
    def get_users_count(self, obj):
        """Hiển thị số lượng users có attribute này"""
        return obj.users_with_attribute.count()
    get_users_count.short_description = 'Users Count'


@admin.register(UserAttribute)
class UserAttributeAdmin(admin.ModelAdmin):
    list_display = ('user', 'attribute', 'assigned_at')
    list_filter = ('attribute', 'assigned_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'attribute__name')
    autocomplete_fields = ('user', 'attribute')
    list_per_page = 50
    
    def get_queryset(self, request):
        """Optimize queries"""
        return super().get_queryset(request).select_related('user', 'attribute')


@admin.register(MedicalData)
class MedicalDataAdmin(admin.ModelAdmin):
    list_display = ('case_id', 'patient_id', 'owner_user', 'created_date', 'created_at')
    list_filter = ('created_date', 'created_at')
    search_fields = ('case_id', 'patient_id', 'owner_user__email', 'owner_user__first_name', 'owner_user__last_name')
    readonly_fields = ('case_id', 'created_at', 'updated_at')
    autocomplete_fields = ('owner_user',)
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('case_id', 'patient_id', 'owner_user', 'created_date')
        }),
        ('Thông tin bệnh nhân (đã mã hóa)', {
            'fields': (
                'patient_info_aes_key_blob',
                'patient_info_aes_iv_blob',
                'patient_id_blob',
                'patient_name_blob',
                'patient_age_blob',
                'patient_gender_blob',
                'patient_phone_blob'
            ),
            'classes': ('collapse',),
            'description': 'Dữ liệu đã được mã hóa bằng AES và CP-ABE'
        }),
        ('Hồ sơ y tế (đã mã hóa)', {
            'fields': (
                'medical_record_aes_key_blob',
                'medical_record_aes_iv_blob',
                'chief_complaint_blob',
                'past_medical_history_blob',
                'diagnosis_blob',
                'status_blob'
            ),
            'classes': ('collapse',),
            'description': 'Dữ liệu đã được mã hóa bằng AES và CP-ABE'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_change_permission(self, request, obj=None):
        """Chỉ cho phép view, không cho edit dữ liệu đã mã hóa"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Cho phép xóa nhưng cần xác nhận"""
        return request.user.is_superuser