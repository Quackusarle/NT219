from rest_framework import serializers
from django.contrib.auth import authenticate

class LoginSerializer(serializers.Serializer):
    """
    Serializer cho login với username và password
    """
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        if username and password:
            # Authenticate user
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid username or password')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
                
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include username and password')

class TokenResponseSerializer(serializers.Serializer):
    """
    Serializer để parse response token từ auth center
    """
    access = serializers.CharField()
    refresh = serializers.CharField()
    user_info = serializers.DictField()

class UserInfoSerializer(serializers.Serializer):
    """
    Serializer cho thông tin user được parse từ token
    """
    username = serializers.CharField()
    email = serializers.EmailField()
    user_attributes = serializers.CharField(allow_blank=True) 
    
from rest_framework import serializers
from .models import ProtectedEHRTextData

class ProtectedEHRTextDataCreateSerializer(serializers.ModelSerializer):
    # Các trường client sẽ gửi lên, khớp với payloadToServer trong JavaScript
    patient_id = serializers.CharField(max_length=100, source='patient_id_on_rs')
    # description, data_type, cpabe_policy_applied,
    # encrypted_kek_b64, aes_iv_b64, encrypted_main_content_b64
    # sẽ được map tự động nếu tên giống nhau.

    class Meta:
        model = ProtectedEHRTextData
        fields = [
            'patient_id',
            'description',
            'data_type',
            'cpabe_policy_applied',
            'encrypted_kek_b64',
            'aes_iv_b64',
            'encrypted_main_content_b64',
        ]

class ProtectedEHRTextDataResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProtectedEHRTextData
        fields = [
            'id',
            'patient_id_on_rs',
            'description',
            'data_type',
            'cpabe_policy_applied',
            'created_by_ac_user_id',
            'created_at',
        ]