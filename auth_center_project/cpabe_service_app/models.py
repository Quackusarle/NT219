# cpabe_service_app/models.py
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

class Attribute(models.Model):
    name = models.CharField(max_length=255, unique=True, help_text="Ví dụ: ROLE:DOCTOR hoặc DEPARTMENT:CARDIO")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Thuộc tính CP-ABE"
        verbose_name_plural = "Các thuộc tính CP-ABE"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cpabe_profile')
    # attributes trỏ đến các Attribute, sẽ lấy ID (số) để sử dụng trong CP-ABE
    attributes = models.ManyToManyField(Attribute, blank=True, verbose_name="Các thuộc tính được gán")

    def __str__(self):
        return f"Hồ sơ CP-ABE của {self.user.username}"

    def get_attributes_string(self):
        # Lấy ID của các thuộc tính, sắp xếp theo số
        attribute_ids = sorted([attr.id for attr in self.attributes.all()])
        return ",".join(map(str, attribute_ids))
        
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)