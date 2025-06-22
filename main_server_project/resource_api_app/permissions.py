from rest_framework.permissions import BasePermission
import logging

logger = logging.getLogger(__name__)

class CanUploadTextDataPermission(BasePermission):
    """
    Permission để kiểm tra xem user có thể upload text data không
    Có thể mở rộng với ABAC logic trong tương lai
    """
    
    def has_permission(self, request, view):
        # Hiện tại chỉ cần user đã được authenticated
        return request.user and request.user.is_authenticated

class CanAccessEHRDataPermission(BasePermission):
    """
    Permission để kiểm tra xem user có thể truy cập EHR data không
    Có thể mở rộng với ABAC logic trong tương lai
    """
    
    def has_permission(self, request, view):
        # Hiện tại chỉ cần user đã được authenticated
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """
        Kiểm tra permission cho object cụ thể
        Có thể implement logic ABAC ở đây
        """
        # Ví dụ: chỉ cho phép user truy cập data mà họ đã tạo
        # hoặc theo policy ABAC phức tạp hơn
        return True  # Tạm thời cho phép tất cả 