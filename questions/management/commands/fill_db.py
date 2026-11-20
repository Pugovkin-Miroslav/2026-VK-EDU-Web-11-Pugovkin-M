from array import array
from datetime import timedelta
from itertools import islice
from random import Random
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from core.models import Profile
from questions.models import Answer, AnswerLike, Question, QuestionLike, Tag


BATCH_SIZE = 5_000
QUESTIONS_PER_USER = 10
ANSWERS_PER_QUESTION = 10
QUESTION_LIKES_PER_USER = 20
ANSWER_LIKES_PER_USER = 180


def _bulk_create(model, objects, *, collect_ids=False):
    rows = iter(objects)
    ids = array('q')
    while batch := list(islice(rows, BATCH_SIZE)):
        created = model.objects.bulk_create(batch, batch_size=BATCH_SIZE)
        if collect_ids:
            ids.extend(obj.pk for obj in created)
    return ids


def _users(user_model, fake, run_id, count):
    for number in range(count):
        user = user_model(
            username=f'demo_{run_id}_{number}',
            first_name=fake.first_name(),
            last_name=fake.last_name(),
        )
        user.set_unusable_password()
        yield user


def _questions(fake, rng, user_ids, count, now):
    for number in range(count):
        yield Question(
            title=fake.sentence(nb_words=6).rstrip('.')[:199] + '?',
            text=fake.text(max_nb_chars=300),
            author_id=rng.choice(user_ids),
            created_at=now - timedelta(minutes=number + 2),
        )


def _tag_links(rng, question_ids, tag_ids):
    through = Question.tags.through
    tag_limit = min(3, len(tag_ids))
    for question_id in question_ids:
        for tag_id in rng.sample(tag_ids, rng.randint(1, tag_limit)):
            yield through(question_id=question_id, tag_id=tag_id)


def _answers(fake, rng, user_ids, question_ids, now):
    # Give the first two questions zero and twice the usual number of answers.
    for index, question_id in enumerate(question_ids[1:], start=1):
        count = 2 * ANSWERS_PER_QUESTION if index == 1 else ANSWERS_PER_QUESTION
        started_at = now - timedelta(minutes=index + 1)
        for offset in range(count):
            yield Answer(
                text=fake.text(max_nb_chars=220),
                author_id=rng.choice(user_ids),
                question_id=question_id,
                is_correct=offset == 0,
                created_at=started_at + timedelta(seconds=offset),
            )


def _likes(model, target_field, rng, user_ids, target_ids, per_user):
    positions = range(len(target_ids))
    for user_id in user_ids:
        for index in rng.sample(positions, per_user):
            yield model(user_id=user_id, **{target_field: target_ids[index]})


class Command(BaseCommand):
    help = 'Добавляет тестовые данные для сайта вопросов и ответов.'

    def add_arguments(self, parser):
        parser.add_argument(
            'ratio', type=int, nargs='?', default=10,
            help='Число новых пользователей и тегов (от 2, по умолчанию 10).',
        )

    def handle(self, *args, **options):
        ratio = options['ratio']
        if ratio < 2:
            raise CommandError('ratio должен быть не меньше 2.')

        fake = Faker('ru_RU')
        rng = Random()
        run_id = uuid4().hex
        now = timezone.now()
        user_model = get_user_model()
        questions_count = ratio * QUESTIONS_PER_USER
        likes_count = ratio * (QUESTION_LIKES_PER_USER + ANSWER_LIKES_PER_USER)

        with transaction.atomic():
            self.stdout.write('Генерация пользователей, профилей и тегов…')
            users = _users(user_model, fake, run_id, ratio)
            user_ids = _bulk_create(user_model, users, collect_ids=True)
            _bulk_create(Profile, (Profile(user_id=user_id) for user_id in user_ids))
            tags = (
                Tag(name=f'{fake.word().capitalize()} {number + 1}', slug=f'demo-{run_id}-{number}')
                for number in range(ratio)
            )
            tag_ids = _bulk_create(Tag, tags, collect_ids=True)

            self.stdout.write('Генерация вопросов и ответов…')
            questions = _questions(fake, rng, user_ids, questions_count, now)
            question_ids = _bulk_create(Question, questions, collect_ids=True)
            _bulk_create(Question.tags.through, _tag_links(rng, question_ids, tag_ids))
            answers = _answers(fake, rng, user_ids, question_ids, now)
            answer_ids = _bulk_create(Answer, answers, collect_ids=True)

            self.stdout.write('Генерация лайков…')
            question_likes = _likes(
                QuestionLike, 'question_id', rng, user_ids, question_ids, QUESTION_LIKES_PER_USER,
            )
            answer_likes = _likes(
                AnswerLike, 'answer_id', rng, user_ids, answer_ids, ANSWER_LIKES_PER_USER,
            )
            _bulk_create(QuestionLike, question_likes)
            _bulk_create(AnswerLike, answer_likes)

        self.stdout.write(self.style.SUCCESS(
            f'Добавлено пользователей, профилей и тегов по {len(user_ids)}, '
            f'вопросов {len(question_ids)}, ответов {len(answer_ids)}, лайков {likes_count}.',
        ))
