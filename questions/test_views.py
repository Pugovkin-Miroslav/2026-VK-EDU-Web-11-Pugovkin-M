from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.models import Profile
from .models import Answer, AnswerLike, Question, QuestionLike, Tag


class EmptyQuestionViewsTests(TestCase):
    def test_empty_database_renders_question_lists(self):
        for path in ('/', '/hot/'):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertContains(response, 'Вопросов пока нет.')
                self.assertNotContains(response, '/tag/python/')

    def test_missing_and_invalid_resources_return_404(self):
        for path in (
            '/tag/missing/', '/question/123/', '/question/abc/',
            '/question/-1/', '/question/9223372036854775808/',
        ):
            with self.subTest(path=path):
                self.assertContains(self.client.get(path), 'Страница не найдена', status_code=404)


class QuestionViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.author = users.create_user(
            username='db-author', first_name='Иван', last_name='Петров',
        )
        cls.reader = users.create_user(username='db-reader')
        Profile.objects.create(user=cls.author, avatar='avatars/author.png')
        cls.tag = Tag.objects.create(name='Базы данных', slug='databases')
        cls.old = Question.objects.create(
            title='Старый вопрос из БД', text='Текст из БД', author=cls.author,
            created_at=timezone.now() - timedelta(days=1),
        )
        cls.new = Question.objects.create(
            title='Новый вопрос из БД', text='Новый текст', author=cls.reader,
        )
        cls.old.tags.add(cls.tag)
        for user in (cls.author, cls.reader):
            QuestionLike.objects.create(question=cls.old, user=user)
        cls.first_answer = Answer.objects.create(
            question=cls.old, author=cls.reader, text='Первый ответ из БД', is_correct=True,
        )
        cls.second_answer = Answer.objects.create(
            question=cls.old, author=cls.author, text='Второй ответ из БД',
        )
        AnswerLike.objects.create(answer=cls.first_answer, user=cls.author)

    def test_newest_popular_and_tag_lists_use_database_data(self):
        for path, expected in (
            ('/', [self.new, self.old]),
            ('/hot/', [self.old, self.new]),
            ('/tag/databases/', [self.old]),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context['page_obj']), expected)
                self.assertContains(response, self.old.get_absolute_url())
                self.assertContains(response, '/tag/databases/')
                self.assertContains(response, 'Базы данных')
                self.assertContains(response, 'Ответы: 2')
                self.assertContains(response, 'Иван Петров')
                self.assertNotContains(response, 'db-author')

    def test_detail_shows_accurate_counts_and_avatars(self):
        response = self.client.get(self.old.get_absolute_url())
        self.assertContains(response, self.old.text)
        self.assertContains(response, '/media/avatars/author.png')
        self.assertContains(response, '/static/core/img/profile-icon.png')
        self.assertContains(response, 'Правильный ответ')
        self.assertContains(response, 'Иван Петров', count=2)
        self.assertContains(response, 'db-reader')
        self.assertNotContains(response, 'db-author')
        question = response.context['question']
        self.assertEqual((question.rating, question.answer_count), (2, 2))
        self.assertEqual([answer.rating for answer in response.context['page_obj']], [1, 0])

    def test_existing_empty_tag_and_question_show_empty_states(self):
        Tag.objects.create(name='Пустой тег', slug='empty')
        self.assertContains(self.client.get('/tag/empty/'), 'Вопросов пока нет.')
        self.assertContains(self.client.get(self.new.get_absolute_url()), 'Ответов пока нет.')

    def test_questions_and_answers_are_paginated_and_invalid_pages_fall_back(self):
        for number in range(10):
            question = Question.objects.create(
                title=f'Дополнительный вопрос {number}', text='Текст', author=self.author,
            )
            question.tags.add(self.tag)
            Answer.objects.create(
                question=self.old, author=self.author, text=f'Дополнительный ответ {number}',
            )
        for path in ('/', '/hot/', '/tag/databases/', self.old.get_absolute_url()):
            with self.subTest(path=path):
                response = self.client.get(path, {'page': 2})
                self.assertContains(response, 'aria-current="page">2')
                self.assertIn(len(response.context['page_obj']), (1, 2))
                for invalid in ('abc', '-1', '999'):
                    page = self.client.get(path, {'page': invalid}).context['page_obj']
                    self.assertEqual(page.number, 1)

    def test_list_and_detail_query_counts_do_not_grow_per_row(self):
        paths = ('/', '/hot/', '/tag/databases/', self.old.get_absolute_url())

        def query_counts():
            counts = []
            for path in paths:
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                counts.append(len(queries))
            return counts

        before = query_counts()
        for number in range(5):
            question = Question.objects.create(
                title=f'Вопрос {number}', text='Текст', author=self.reader,
            )
            question.tags.add(self.tag)
            Answer.objects.create(question=self.old, text='Ответ', author=self.reader)
        self.assertEqual(query_counts(), before)

    def test_large_list_keeps_first_and_last_page_links(self):
        Question.objects.bulk_create([
            Question(title=f'Вопрос {number}', text='Текст', author=self.author)
            for number in range(300)
        ])

        response = self.client.get('/', {'page': 15})

        self.assertContains(response, 'href="?page=1"')
        self.assertContains(response, 'href="?page=31"')
        self.assertContains(response, 'aria-current="page">15')
        self.assertLessEqual(response.content.count(b'href="?page='), 6)
