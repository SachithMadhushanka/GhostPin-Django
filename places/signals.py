from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .models import Notification
from django.utils.timezone import now
from datetime import timedelta

@receiver(user_logged_in)
def send_welcome_notification(sender, request, user, **kwargs):
    # Check if welcome notification already sent
    already_sent = Notification.objects.filter(
        user=user,
        notification_type='welcome',
    ).exists()

    if not already_sent:
        Notification.objects.create(
            user=user,
            title="Welcome Back!",
            message="We're glad to see you again. Ready to explore new places?",
            notification_type="welcome"
        )

