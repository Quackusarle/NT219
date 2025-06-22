from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework import status
from django.http import HttpResponse, Http404
from django.conf import settings
from django.shortcuts import render
from .cpabe_handler import CPABEHandler
from .models import UserProfile
from .serializers import MyTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class CPABESetupView(APIView):
    permission_classes = [IsAdminUser] # Chỉ admin Django mới được setup

    def post(self, request, *args, **kwargs):
        handler = CPABEHandler()
        success, message = handler.run_system_setup()
        if success:
            return Response({"message": message}, status=status.HTTP_200_OK)
        else:
            # Nếu message chứa "đã được thiết lập", vẫn trả về 200
            if "đã được thiết lập" in message:
                 return Response({"message": message}, status=status.HTTP_200_OK)
            return Response({"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PublicKeyView(APIView):
    permission_classes = [AllowAny] # Khóa công khai cho phép mọi người truy cập

    def get(self, request, *args, **kwargs):
        handler = CPABEHandler()
        pk_content, error_msg = handler.get_public_key_content()

        if error_msg:
            return Response({"error": error_msg}, status=status.HTTP_404_NOT_FOUND)

        # Trả về file Khóa Công Khai
        response = HttpResponse(pk_content, content_type='application/octet-stream')
        # Lấy tên file từ settings để client có thể lưu đúng tên
        pk_filename = settings.CPABE_CONFIG['PUBLIC_KEY_FILENAME']
        response['Content-Disposition'] = f'attachment; filename="{pk_filename}"'
        return response

class GenerateSecretKeyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return Response({"error": "Không tìm thấy hồ sơ người dùng CP-ABE."}, status=status.HTTP_404_NOT_FOUND)

        user_attributes_str = user_profile.get_attributes_string()

        if not user_attributes_str:
            return Response({"error": "Người dùng chưa được gán thuộc tính nào."}, status=status.HTTP_400_BAD_REQUEST)

        print(f"Đang tạo Khóa Bí Mật cho người dùng '{user.username}' với thuộc tính: '{user_attributes_str}'")
        handler = CPABEHandler()
        sk_content, error_msg = handler.generate_secret_key_content(user_attributes_str)

        if error_msg:
            return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        response = HttpResponse(sk_content, content_type='application/octet-stream')
        response['Content-Disposition'] = 'attachment; filename="secret_key.bin"'
        return response

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view để sử dụng serializer có attributes
    """
    serializer_class = MyTokenObtainPairSerializer