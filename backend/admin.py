from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, Attribute, UserAttribute, AccessPolicy, ProtectedData
# Register your models here.


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'created_at', 'last_login')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'last_login', 'last_login_ip')
    
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
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at',)
    ordering = ('name',)

@admin.register(UserAttribute)
class UserAttributeAdmin(admin.ModelAdmin):
    list_display = ('user', 'attribute', 'assigned_at')
    list_filter = ('attribute', 'assigned_at')
    search_fields = ('user__email', 'attribute__name')
    autocomplete_fields = ('user', 'attribute')

@admin.register(AccessPolicy)
class AccessPolicyAdmin(admin.ModelAdmin):
    list_display = ('name', 'policy_definition', 'created_at', 'updated_at')
    search_fields = ('name', 'policy_definition', 'description')
    list_filter = ('created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ProtectedData)
class ProtectedDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'owner_user', 'policy', 'filename', 'mime_type', 'uploaded_at')
    list_filter = ('policy', 'mime_type', 'uploaded_at')
    search_fields = ('filename', 'description', 'owner_user__email')
    readonly_fields = ('uploaded_at', 'updated_at')
    autocomplete_fields = ('owner_user', 'policy')