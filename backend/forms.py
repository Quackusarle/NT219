from django import forms
from allauth.account.forms import SignupForm
from .models import User

class CustomSignupForm(SignupForm):
    """
    Custom signup form to add additional fields or validation.
    """
    first_name = forms.CharField(max_length=30, required=True, label='First Name')
    last_name = forms.CharField(max_length=30, required=True, label='Last Name')

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save()
        return user