from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Attribute, UserAttribute, AccessPolicy, ProtectedData


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


@admin.register(AccessPolicy)
class AccessPolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'policy_template', 'created_at', 'updated_at')
    search_fields = ('name', 'policy_template', 'description')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'description')
        }),
        ('Policy Configuration', {
            'fields': ('policy_template',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProtectedData)
class ProtectedDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner_user', 'policy_template', 'filename', 'mime_type', 'uploaded_at')
    list_filter = ('policy_template', 'mime_type', 'uploaded_at')
    search_fields = ('filename', 'description', 'owner_user__email')
    readonly_fields = ('uploaded_at', 'updated_at')
    autocomplete_fields = ('owner_user', 'policy_template')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('owner_user', 'filename', 'description', 'mime_type', 'file_size')
        }),
        ('Policy & Access', {
            'fields': ('policy_template',)
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