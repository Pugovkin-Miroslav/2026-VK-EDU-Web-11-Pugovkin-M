from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction

from .models import Profile


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
