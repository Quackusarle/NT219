from .models import UserAttribute

def user_attributes_context(request):
    """
    Context processor để thêm thông tin attributes vào tất cả templates
    """
    context = {}
    
    if request.user.is_authenticated:
        # Kiểm tra user có attributes hay không
        has_attributes = UserAttribute.objects.filter(user=request.user).exists()
        user_attributes = UserAttribute.objects.filter(user=request.user)
        
        # Kiểm tra user có phải bác sĩ không
        is_doctor = UserAttribute.objects.filter(
            user=request.user,
            attribute__name__in=['doctor', 'bac_si', 'bác sĩ']
        ).exists()
        
        context.update({
            'has_attributes': has_attributes,
            'user_attributes': user_attributes,
            'is_doctor': is_doctor,
        })
    else:
        context.update({
            'has_attributes': False,
            'user_attributes': None,
            'is_doctor': False,
        })
    
    return context 