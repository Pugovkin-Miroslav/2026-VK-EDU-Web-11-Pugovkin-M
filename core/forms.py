from pathlib import Path

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import transaction

from .models import Profile

AVATAR_FORMATS = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP'}
AVATAR_SIZE_LIMIT_MB = 2
AVATAR_SIZE_LIMIT_BYTES = AVATAR_SIZE_LIMIT_MB * 1024 * 1024
AVATAR_SIZE_ERROR = f'Размер аватара не должен превышать {AVATAR_SIZE_LIMIT_MB} МБ.'


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Логин'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email', 'first_name')
        labels = {'username': 'Логин', 'first_name': 'Имя'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['first_name'].required = True
        self.fields['first_name'].widget.attrs['autocomplete'] = 'given-name'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Profile.objects.create(user=user)
        return user


class ProfileForm(forms.Form):
    email = forms.EmailField(
        label='Email', max_length=254,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )
    nick = forms.CharField(
        label='Ник', max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'nickname'}),
    )
    avatar = forms.ImageField(
        label='Аватар', required=False,
        help_text=f'JPG, PNG или WebP до {AVATAR_SIZE_LIMIT_MB} МБ.',
        validators=[FileExtensionValidator(allowed_extensions=tuple(AVATAR_FORMATS))],
        widget=forms.FileInput(attrs={
            'class': 'form-control', 'accept': 'image/jpeg,image/png,image/webp',
            'data-avatar-max-bytes': AVATAR_SIZE_LIMIT_BYTES,
            'data-avatar-size-error': AVATAR_SIZE_ERROR,
        }),
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        kwargs.setdefault('initial', {'email': user.email, 'nick': user.first_name})
        super().__init__(*args, **kwargs)

    def clean_avatar(self):
        avatar = self.cleaned_data['avatar']
        if avatar is None:
            return None
        if avatar.size > AVATAR_SIZE_LIMIT_BYTES:
            raise ValidationError(AVATAR_SIZE_ERROR, code='file_too_large')
        extension = Path(avatar.name).suffix.lower().lstrip('.')
        if avatar.image.format != AVATAR_FORMATS[extension]:
            raise ValidationError(
                'Расширение файла не соответствует формату изображения.',
                code='invalid_image_format',
            )
        return avatar

    @transaction.atomic
    def save(self):
        self.user.email = self.cleaned_data['email']
        self.user.first_name = self.cleaned_data['nick']
        self.user.save(update_fields=['email', 'first_name'])

        profile, _ = Profile.objects.get_or_create(user=self.user)
        avatar = self.cleaned_data['avatar']
        if avatar is not None:
            profile.avatar = avatar
            profile.save(update_fields=['avatar'])
        return profile
