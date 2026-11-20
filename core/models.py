from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.db import models


def avatar_upload_path(_profile, filename):
    extension = Path(filename).suffix.lower()
    return f'avatars/{uuid4().hex}{extension}'


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='пользователь',
    )
    avatar = models.ImageField('аватар', upload_to=avatar_upload_path, blank=True)

    class Meta:
        verbose_name = 'профиль'
        verbose_name_plural = 'профили'

    def __str__(self) -> str:
        return self.user.get_username()
