from hashlib import sha256
from itertools import count

from django import forms
from django.db import transaction
from django.db.models import Sum
from django.utils.text import slugify

from .models import Answer, Question, Tag, VoteValue


TAG_NAME_MAX_LENGTH = Tag._meta.get_field('name').max_length
TAG_SLUG_MAX_LENGTH = Tag._meta.get_field('slug').max_length
MAX_OBJECT_ID = 2**63 - 1


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


class VoteForm(forms.Form):
    id = forms.IntegerField(min_value=1, max_value=MAX_OBJECT_ID)
    value = forms.TypedChoiceField(choices=[*VoteValue.choices, (0, 'Убрать голос')], coerce=int)

    @transaction.atomic
    def save(self, *, target_model, user):
        target = target_model.objects.select_for_update(no_key=True).filter(pk=self.cleaned_data['id']).first()
        if target is None:
            raise forms.ValidationError('Объект для голосования не найден.', code='not_found')

        value = self.cleaned_data['value']
        if value == 0:
            target.likes.filter(user=user).delete()
        else:
            vote, created = target.likes.get_or_create(user=user, defaults={'value': value})
            if not created:
                if vote.value == value:
                    raise forms.ValidationError('Вы уже поставили эту оценку.', code='conflict')
                vote.value = value
                vote.save(update_fields=['value'])

        rating = target.likes.aggregate(rating=Sum('value', default=0))['rating']
        return {'rating': rating, 'value': value}


class CorrectAnswerForm(forms.Form):
    question_id = forms.IntegerField(min_value=1, max_value=MAX_OBJECT_ID)
    answer_id = forms.IntegerField(min_value=1, max_value=MAX_OBJECT_ID)

    @transaction.atomic
    def save(self, *, user):
        question = Question.objects.select_for_update(no_key=True).filter(
            pk=self.cleaned_data['question_id'],
        ).first()
        if question is None:
            raise forms.ValidationError('Вопрос не найден.', code='not_found')
        if question.author_id != user.pk:
            raise forms.ValidationError(
                'Только автор вопроса может выбрать правильный ответ.', code='permission_denied',
            )

        answer = question.answers.select_for_update(no_key=True).filter(
            pk=self.cleaned_data['answer_id'],
        ).first()
        if answer is None:
            raise forms.ValidationError('Ответ не найден в этом вопросе.', code='not_found')
        if answer.is_correct:
            raise forms.ValidationError('Этот ответ уже отмечен правильным.', code='conflict')

        question.answers.filter(is_correct=True).update(is_correct=False)
        answer.is_correct = True
        answer.save(update_fields=['is_correct'])
        return {'answer_id': answer.pk}
