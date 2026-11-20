from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.models import Count
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.models import Profile

from .management.commands import fill_db
from .models import Answer, AnswerLike, Question, QuestionLike, Tag


class FillDatabaseTests(TestCase):
    def test_fill_db_adds_exact_counts_on_each_run(self):
        users = get_user_model().objects
        existing_user = users.create_user(username='existing')

        for run in (1, 2):
            call_command('fill_db', 2, stdout=StringIO())

            self.assertEqual(users.count(), 1 + 2 * run)
            self.assertEqual(Profile.objects.count(), 2 * run)
            self.assertEqual(Tag.objects.count(), 2 * run)
            self.assertEqual(Question.objects.count(), 20 * run)
            self.assertEqual(Answer.objects.count(), 200 * run)
            self.assertEqual(QuestionLike.objects.count(), 40 * run)
            self.assertEqual(AnswerLike.objects.count(), 360 * run)

        self.assertTrue(users.filter(pk=existing_user.pk, username='existing').exists())
        self.assertTrue(all(
            user.first_name and user.last_name and not user.has_usable_password()
            for user in users.exclude(pk=existing_user.pk)
        ))

        questions = Question.objects.annotate(answers_total=Count('answers'))
        self.assertTrue(questions.filter(answers_total=0).exists())
        self.assertTrue(questions.filter(answers_total__gt=10).exists())
        self.assertFalse(Question.objects.filter(tags__isnull=True).exists())

    def test_fill_db_uses_batched_queries(self):
        with CaptureQueriesContext(connection) as queries:
            call_command('fill_db', 30, stdout=StringIO())

        self.assertEqual(Question.objects.count(), 300)
        self.assertEqual(AnswerLike.objects.count(), 5400)
        self.assertLessEqual(len(queries), 16)

    def test_fill_db_rejects_ratio_below_two(self):
        with self.assertRaisesMessage(CommandError, 'ratio должен быть не меньше 2'):
            call_command('fill_db', 1, stdout=StringIO())

        self.assertFalse(get_user_model().objects.exists())

    def test_failed_run_rolls_back_before_a_retry(self):
        bulk_create = fill_db._bulk_create

        def fail_on_answer_likes(model, *args, **kwargs):
            if model is AnswerLike:
                raise RuntimeError('Ошибка на этапе лайков ответов')
            return bulk_create(model, *args, **kwargs)

        with patch.object(fill_db, '_bulk_create', side_effect=fail_on_answer_likes):
            with self.assertRaisesMessage(RuntimeError, 'Ошибка на этапе лайков ответов'):
                call_command('fill_db', 2, stdout=StringIO())

        for model in (get_user_model(), Profile, Tag, Question, Answer, QuestionLike, AnswerLike):
            self.assertFalse(model.objects.exists(), model._meta.label)

        call_command('fill_db', 2, stdout=StringIO())
        self.assertEqual(get_user_model().objects.count(), 2)
        self.assertEqual(AnswerLike.objects.count(), 360)
