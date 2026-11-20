from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import resolve, reverse

from .models import Answer, AnswerLike, Question, QuestionLike, Tag


class QuestionModelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.author = users.create_user(username='author')
        cls.reader = users.create_user(username='reader')
        cls.question = Question.objects.create(
            title='Как работает Django ORM?', text='Пример вопроса.', author=cls.author,
        )
        cls.answer = Answer.objects.create(
            text='ORM преобразует операции с моделями в запросы к БД.',
            question=cls.question,
            author=cls.reader,
        )

    def test_question_links_to_detail_answers_and_tags(self):
        tag = Tag.objects.create(name='Django', slug='django')
        self.question.tags.add(tag)

        match = resolve(self.question.get_absolute_url())
        self.assertEqual(match.view_name, 'questions:detail')
        self.assertEqual(match.kwargs, {'pk': self.question.pk})
        self.assertEqual(list(self.question.answers.all()), [self.answer])
        self.assertEqual(list(tag.questions.all()), [self.question])

    def test_tag_rejects_a_slug_that_cannot_be_used_in_its_url(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tag.objects.create(name='Джанго', slug='джанго')

    def test_question_like_is_unique_per_user_and_question(self):
        other_question = Question.objects.create(
            title='Другой вопрос', text='Описание.', author=self.author,
        )
        QuestionLike.objects.create(user=self.reader, question=self.question)
        QuestionLike.objects.create(user=self.author, question=self.question)
        QuestionLike.objects.create(user=self.reader, question=other_question)

        with self.assertRaises(IntegrityError), transaction.atomic():
            QuestionLike.objects.create(user=self.reader, question=self.question)

    def test_answer_like_is_unique_per_user_and_answer(self):
        other_answer = Answer.objects.create(
            text='Другой ответ.', question=self.question, author=self.author,
        )
        AnswerLike.objects.create(user=self.reader, answer=self.answer)
        AnswerLike.objects.create(user=self.author, answer=self.answer)
        AnswerLike.objects.create(user=self.reader, answer=other_answer)

        with self.assertRaises(IntegrityError), transaction.atomic():
            AnswerLike.objects.create(user=self.reader, answer=self.answer)


class QuestionAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin_user = users.create_superuser(username='admin')
        cls.author = users.create_user(username='author')
        cls.question = Question.objects.create(
            title='Как настроить админку?',
            text='Вопрос о Django.',
            author=cls.author,
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_question_can_be_created_and_changed_in_admin(self):
        tag = Tag.objects.create(name='Django', slug='django')
        form = {
            'title': 'Новый вопрос',
            'text': 'Текст вопроса.',
            'author': self.author.pk,
            'tags': [tag.pk],
            'created_at_0': '2026-11-20',
            'created_at_1': '12:00:00',
            '_save': '1',
        }
        response = self.client.post(reverse('admin:questions_question_add'), form)
        self.assertRedirects(response, reverse('admin:questions_question_changelist'))
        question = Question.objects.get(title=form['title'])
        self.assertEqual(list(question.tags.all()), [tag])

        form.update(text='Обновлённый текст.', **{
            'answers-TOTAL_FORMS': '0',
            'answers-INITIAL_FORMS': '0',
        })
        change_url = reverse('admin:questions_question_change', args=[question.pk])
        response = self.client.post(change_url, form)
        self.assertRedirects(response, reverse('admin:questions_question_changelist'))
        question.refresh_from_db()
        self.assertEqual(question.text, 'Обновлённый текст.')

    def test_question_change_links_to_its_public_database_record(self):
        url = reverse('admin:questions_question_change', args=[self.question.pk])
        response = self.client.get(url)

        public_page = self.client.get(response.context['absolute_url'], follow=True)
        self.assertEqual(public_page.request['PATH_INFO'], self.question.get_absolute_url())
        self.assertContains(public_page, self.question.title)

    def test_answer_inline_query_count_does_not_grow_with_answers(self):
        change_url = reverse('admin:questions_question_change', args=[self.question.pk])
        answer = Answer.objects.create(
            question=self.question, author=self.author, text='Первый ответ.',
        )
        self.client.get(change_url)

        with CaptureQueriesContext(connection) as one_answer:
            response = self.client.get(change_url)
        self.assertContains(response, answer.text)
        self.assertContains(response, reverse('admin:questions_answer_change', args=[answer.pk]))

        Answer.objects.bulk_create([
            Answer(question=self.question, author=self.author, text=f'Ответ {number}.')
            for number in range(5)
        ])
        with CaptureQueriesContext(connection) as six_answers:
            response = self.client.get(change_url)
        self.assertContains(response, 'Ответ 4.')
        self.assertEqual(len(six_answers), len(one_answer))

    def test_question_save_query_count_does_not_grow_with_answers(self):
        url = reverse('admin:questions_question_change', args=[self.question.pk])
        answer = Answer.objects.create(
            question=self.question, author=self.author, text='Первый ответ.',
        )

        def count_save_queries(answer_ids):
            form = {
                'title': self.question.title,
                'text': self.question.text,
                'author': self.author.pk,
                'created_at_0': '2026-11-20',
                'created_at_1': '12:00:00',
                'answers-TOTAL_FORMS': str(len(answer_ids)),
                'answers-INITIAL_FORMS': str(len(answer_ids)),
                '_save': '1',
            }
            for number, answer_id in enumerate(answer_ids):
                form[f'answers-{number}-id'] = answer_id
            with CaptureQueriesContext(connection) as queries:
                response = self.client.post(url, form)
            self.assertEqual(response.status_code, 302)
            return len(queries)

        count_save_queries([answer.pk])
        one_answer = count_save_queries([answer.pk])
        more_answers = Answer.objects.bulk_create([
            Answer(question=self.question, author=self.author, text=f'Ответ {number}.')
            for number in range(5)
        ])
        six_answers = count_save_queries([answer.pk, *(item.pk for item in more_answers)])
        self.assertEqual(six_answers, one_answer)
