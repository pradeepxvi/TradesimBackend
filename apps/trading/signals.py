from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.users.models import User

from .models import Wallet


@receiver(post_save, sender=User)
def create_verified_user_wallet(sender, instance, **kwargs):
    if instance.is_verified:
        Wallet.objects.get_or_create(
            user=instance,
            defaults={"virtual_balance": settings.INITIAL_VIRTUAL_BALANCE},
        )
