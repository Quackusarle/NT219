from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Attribute, UserAttribute, AccessPolicy, ProtectedData
# Register your models here.


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'patient_id', 'first_name', 'last_name', 'is_active', 'is_staff', 'created_at', 'last_login')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'patient_id')
    ordering = ('-created_at',)
    readonly_fields = ('patient_id', 'created_at', 'updated_at', 'last_login', 'last_login_ip')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'patient_id')}),
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
    list_display = ('name', 'supports_patient_id', 'description', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('supports_patient_id', 'created_at')
    ordering = ('name',)

@admin.register(UserAttribute)
class UserAttributeAdmin(admin.ModelAdmin):
    list_display = ('user', 'attribute', 'patient_id', 'full_attribute_name', 'assigned_at')
    list_filter = ('attribute', 'assigned_at')
    search_fields = ('user__email', 'attribute__name', 'patient_id')
    autocomplete_fields = ('user', 'attribute')
    
    def full_attribute_name(self, obj):
        return obj.full_attribute_name
    full_attribute_name.short_description = 'Full Attribute'

@admin.register(AccessPolicy)
class AccessPolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'policy_type', 'policy_template', 'created_at', 'updated_at')
    search_fields = ('name', 'policy_template', 'description')
    list_filter = ('policy_type', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_required_placeholders_display(self, obj):
        return ', '.join(obj.get_required_placeholders())
    get_required_placeholders_display.short_description = 'Required Placeholders'

@admin.register(ProtectedData)
class ProtectedDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner_user', 'policy_template', 'target_patient_id', 'filename', 'mime_type', 'uploaded_at')
    list_filter = ('policy_template', 'mime_type', 'uploaded_at')
    search_fields = ('filename', 'description', 'owner_user__email', 'target_patient_id')
    readonly_fields = ('rendered_policy', 'uploaded_at', 'updated_at')
    autocomplete_fields = ('owner_user', 'policy_template')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('owner_user', 'filename', 'description', 'mime_type', 'file_size')
        }),
        ('Policy & Access', {
            'fields': ('policy_template', 'target_patient_id', 'rendered_policy')
        }),
        ('Encrypted Data', {
            'fields': ('abe_encrypted_aes_key_blob', 'aes_iv_for_content', 'encrypted_content_blob'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('uploaded_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )