from django.conf import settings
from django.db import models
from django.db.models import Count, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from .pagination import PAGE_SIZE


def _aggregate_related(model, foreign_key, aggregate):
    totals = (
        model.objects.filter(**{foreign_key: OuterRef('pk')})
        .order_by()
        .values(foreign_key)
        .annotate(total=aggregate)
        .values('total')
    )
    return Coalesce(Subquery(totals), Value(0), output_field=models.IntegerField())


def _with_user_vote(queryset, vote_model, foreign_key, user):
    if user is None or not user.is_authenticated:
        return queryset
    vote = vote_model.objects.filter(**{foreign_key: OuterRef('pk')}, user_id=user.pk)
    return queryset.annotate(user_vote=Subquery(vote.values('value')))


class TagManager(models.Manager):
    def popular(self):
        return (
            self.annotate(question_count=Count('questions'))
            .filter(question_count__gt=0)
            .order_by('-question_count', 'name', 'pk')[:5]
        )


class QuestionManager(models.Manager):
    def with_card_data(self, user=None):
        queryset = (
            self.select_related('author__profile')
            .prefetch_related('tags')
            .annotate(
                rating=_aggregate_related(QuestionLike, 'question_id', Sum('value')),
                answer_count=_aggregate_related(Answer, 'question_id', Count('*')),
            )
        )
        return _with_user_vote(queryset, QuestionLike, 'question_id', user)

    def newest(self, user=None):
        return self.with_card_data(user).order_by('-created_at', '-pk')

    def popular(self, user=None):
        return self.with_card_data(user).order_by('-rating', '-created_at', '-pk')

    def for_tag(self, tag, user=None):
        return self.newest(user).filter(tags=tag)


class AnswerManager(models.Manager):
    def for_question(self, question, user=None):
        queryset = (
            self.filter(question=question)
            .select_related('author__profile')
            .annotate(rating=_aggregate_related(AnswerLike, 'answer_id', Sum('value')))
            .order_by('created_at', 'pk')
        )
        return _with_user_vote(queryset, AnswerLike, 'answer_id', user)


class Tag(models.Model):
    name = models.CharField('название', max_length=80)
    slug = models.SlugField('метка для URL', max_length=80, unique=True)
    created_at = models.DateTimeField('дата создания', default=timezone.now)
    objects = TagManager()

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
    objects = QuestionManager()

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
    objects = AnswerManager()

    class Meta:
        verbose_name = 'ответ'
        verbose_name_plural = 'ответы'
        constraints = [
            models.UniqueConstraint(
                fields=['question'], condition=models.Q(is_correct=True),
                name='one_correct_answer_per_question',
            ),
        ]
        indexes = [
            models.Index(
                fields=['question', 'created_at', 'id'],
                name='answer_question_created_idx',
            ),
        ]

    def __str__(self) -> str:
        return self.text[:80]

    def get_absolute_url(self) -> str:
        earlier_answers = Answer.objects.filter(question_id=self.question_id).filter(
            models.Q(created_at__lt=self.created_at)
            | models.Q(created_at=self.created_at, pk__lt=self.pk)
        ).count()
        page = earlier_answers // PAGE_SIZE + 1
        return reverse(
            'questions:detail',
            kwargs={'pk': self.question_id},
            query={'page': page} if page > 1 else None,
            fragment=f'answer-{self.pk}',
        )


class VoteValue(models.IntegerChoices):
    DISLIKE = -1, 'Дизлайк'
    LIKE = 1, 'Лайк'


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
    value = models.SmallIntegerField('оценка', choices=VoteValue.choices, default=VoteValue.LIKE)
    created_at = models.DateTimeField('дата создания', default=timezone.now)

    class Meta:
        verbose_name = 'голос за вопрос'
        verbose_name_plural = 'голоса за вопросы'
        unique_together = [('question', 'user')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(value__in=VoteValue.values), name='question_like_value_valid',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.get_value_display()} вопроса №{self.question_id} от пользователя №{self.user_id}'


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
    value = models.SmallIntegerField('оценка', choices=VoteValue.choices, default=VoteValue.LIKE)
    created_at = models.DateTimeField('дата создания', default=timezone.now)

    class Meta:
        verbose_name = 'голос за ответ'
        verbose_name_plural = 'голоса за ответы'
        unique_together = [('answer', 'user')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(value__in=VoteValue.values), name='answer_like_value_valid',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.get_value_display()} ответа №{self.answer_id} от пользователя №{self.user_id}'
