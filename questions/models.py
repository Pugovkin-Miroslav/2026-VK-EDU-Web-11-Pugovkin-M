from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Tag(models.Model):
    name = models.CharField('название', max_length=80)
    slug = models.SlugField('метка для URL', max_length=80, unique=True)
    created_at = models.DateTimeField('дата создания', default=timezone.now)

    class Meta:
        verbose_name = 'тег'
        verbose_name_plural = 'теги'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(slug__regex=r'^[A-Za-z0-9_-]+$'),
                name='tag_slug_matches_url',
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Question(models.Model):
    title = models.CharField('заголовок', max_length=200)
    text = models.TextField('текст')
    created_at = models.DateTimeField('дата создания', default=timezone.now)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='автор',
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='questions',
        blank=True,
        verbose_name='теги',
    )

    class Meta:
        verbose_name = 'вопрос'
        verbose_name_plural = 'вопросы'
        indexes = [
            models.Index(fields=['-created_at', '-id'], name='question_created_idx'),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse('questions:detail', kwargs={'pk': self.pk})


class Answer(models.Model):
    text = models.TextField('текст')
    created_at = models.DateTimeField('дата создания', default=timezone.now)
    is_correct = models.BooleanField('правильный ответ', default=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='автор',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='вопрос',
    )

    class Meta:
        verbose_name = 'ответ'
        verbose_name_plural = 'ответы'
        indexes = [
            models.Index(
                fields=['question', 'created_at', 'id'],
                name='answer_question_created_idx',
            ),
        ]

    def __str__(self) -> str:
        return self.text[:80]


class QuestionLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_likes',
        verbose_name='пользователь',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name='вопрос',
    )
    created_at = models.DateTimeField('дата создания', default=timezone.now)

    class Meta:
        verbose_name = 'лайк вопроса'
        verbose_name_plural = 'лайки вопросов'
        unique_together = [('question', 'user')]

    def __str__(self) -> str:
        return f'Лайк вопроса №{self.question_id} от пользователя №{self.user_id}'


class AnswerLike(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='answer_likes',
        verbose_name='пользователь',
    )
    answer = models.ForeignKey(
        Answer,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name='ответ',
    )
    created_at = models.DateTimeField('дата создания', default=timezone.now)

    class Meta:
        verbose_name = 'лайк ответа'
        verbose_name_plural = 'лайки ответов'
        unique_together = [('answer', 'user')]

    def __str__(self) -> str:
        return f'Лайк ответа №{self.answer_id} от пользователя №{self.user_id}'
