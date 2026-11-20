from hashlib import sha256
from itertools import count

from django import forms
from django.db import transaction
from django.utils.text import slugify

from .models import Answer, Question, Tag


TAG_NAME_MAX_LENGTH = Tag._meta.get_field('name').max_length
TAG_SLUG_MAX_LENGTH = Tag._meta.get_field('slug').max_length


def _get_or_create_tag(name):
    existing_tag = Tag.objects.filter(name__iexact=name).order_by('pk').first()
    if existing_tag is not None:
        return existing_tag

    normalized_name = name.casefold()
    base_slug = slugify(name)[:TAG_SLUG_MAX_LENGTH]
    if not base_slug:
        digest = sha256(normalized_name.encode()).hexdigest()[:12]
        base_slug = f'tag-{digest}'

    slug = base_slug
    for number in count(2):
        tag, _ = Tag.objects.get_or_create(slug=slug, defaults={'name': name})
        if tag.name.casefold() == normalized_name:
            return tag
        suffix = f'-{number}'
        slug = base_slug[:TAG_SLUG_MAX_LENGTH - len(suffix)] + suffix


class QuestionForm(forms.ModelForm):
    text = forms.CharField(
        label='Текст вопроса', max_length=5000,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
    )
    tags = forms.CharField(
        label='Теги', max_length=100, required=False,
        help_text='Разделяйте теги запятыми.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Python, Django'}),
    )

    class Meta:
        model = Question
        fields = ('title', 'text', 'tags')
        labels = {'title': 'Заголовок'}
        widgets = {'title': forms.TextInput(attrs={'class': 'form-control'})}

    def __init__(self, *args, author, **kwargs):
        self.author = author
        super().__init__(*args, **kwargs)

    def clean_tags(self):
        names = {}
        for part in self.cleaned_data['tags'].split(','):
            name = part.strip()
            if len(name) > TAG_NAME_MAX_LENGTH:
                raise forms.ValidationError(
                    f'Название каждого тега должно содержать не больше {TAG_NAME_MAX_LENGTH} символов.',
                    code='tag_too_long',
                )
            if name:
                names.setdefault(name.casefold(), name)
        return list(names.values())

    @transaction.atomic
    def save(self, commit=True):
        self.instance.author = self.author
        return super().save(commit=commit)

    def _save_m2m(self):
        names = sorted(self.cleaned_data['tags'], key=str.casefold)
        self.instance.tags.set([_get_or_create_tag(name) for name in names])


class AnswerForm(forms.ModelForm):
    class Meta:
        model = Answer
        fields = ('text',)
        labels = {'text': 'Ваш ответ'}
        widgets = {'text': forms.Textarea(attrs={
            'class': 'form-control', 'rows': 5, 'placeholder': 'Введите ответ',
        })}

    def save(self, commit=True, *, question, author):
        self.instance.question = question
        self.instance.author = author
        return super().save(commit=commit)
