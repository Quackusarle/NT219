from django.dispatch import receiver
from allauth.account.models import EmailAddress
from allauth.account.signals import email_added, user_signed_up

@receiver(email_added)
def auto_verify_email_on_add(sender, request, email_address, **kwargs):
    """
    Automatically verifies an email address when it's added,
    if ACCOUNT_EMAIL_VERIFICATION is 'none'.
    """
    if EmailAddress.objects.filter(email=email_address.email, user=email_address.user).exists():
        email_address.verified = True
        email_address.primary = True # Optionally make it primary immediately
        email_address.save()
        print(f"Email {email_address.email} for user {email_address.user} auto-verified on add.")

@receiver(user_signed_up)
def auto_verify_email_on_signup(sender, request, user, **kwargs):
    """
    Automatically verifies the user's email address upon signup,
    if ACCOUNT_EMAIL_VERIFICATION is 'none'.
    """
    try:
        email_address = EmailAddress.objects.get_primary(user)
        if email_address and not email_address.verified:
            email_address.verified = True
            email_address.save()
            print(f"Email {email_address.email} for user {user} auto-verified on signup.")
    except EmailAddress.DoesNotExist:
        # This case should ideally be handled by email_added signal
        # or by ensuring an email address is created during signup.
        # If using CustomSignupForm, an email address should already exist.
        print(f"No primary email found for user {user} during signup for auto-verification.")
    except Exception as e:
        print(f"Error auto-verifying email for {user} on signup: {e}")