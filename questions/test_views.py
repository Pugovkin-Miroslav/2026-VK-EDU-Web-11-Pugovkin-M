from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase
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


class AskQuestionTests(TestCase):
    question_data = {'title': 'Как работает Django?', 'text': 'Текст моего вопроса'}

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='question-author')

    def test_guest_sees_disabled_ask_button_and_is_redirected_to_login(self):
        url = reverse('questions:ask')

        self.assertRedirects(self.client.get(url), '/login/?next=/ask/')
        self.assertRedirects(self.client.post(url, self.question_data), '/login/?next=/ask/')
        homepage = self.client.get('/')
        self.assertContains(homepage, 'title="Войдите, чтобы задать вопрос"')
        self.assertContains(
            homepage, '<button type="button" class="btn btn-primary" disabled>Задать вопрос</button>',
            html=True,
        )
        self.assertFalse(Question.objects.exists())

    def test_publish_reuses_tags_and_handles_cyrillic_and_slug_collisions(self):
        existing_tag = Tag.objects.create(name='Python', slug='python-existing')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse('questions:ask')
        data = {**self.question_data, 'tags': ' python, PYTHON, Базы данных, базы данных, C++, C# '}

        self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.post(url, data).status_code, 403)
        response = client.post(url, {**data, 'csrfmiddlewaretoken': client.cookies['csrftoken'].value})

        self.assertEqual(response.status_code, 302)
        question = Question.objects.get()
        self.assertRedirects(response, question.get_absolute_url())
        self.assertEqual(question.author, self.user)
        self.assertEqual(question.title, self.question_data['title'])
        self.assertEqual(question.text, self.question_data['text'])
        self.assertIn(existing_tag, question.tags.all())
        self.assertCountEqual(question.tags.values_list('name', flat=True), [
            'Python', 'Базы данных', 'C++', 'C#',
        ])
        for tag in question.tags.all():
            self.assertContains(self.client.get(reverse('questions:tag', args=[tag.slug])), question.title)

    def test_invalid_tag_preserves_entered_values_without_creating_records(self):
        self.client.force_login(self.user)
        invalid_tag = 'x' * 81

        response = self.client.post(reverse('questions:ask'), {**self.question_data, 'tags': invalid_tag})

        form = response.context.get('form')
        self.assertIsNotNone(form)
        self.assertTrue(form.has_error('tags'))
        self.assertContains(response, form['tags'].errors[0])
        self.assertContains(response, self.question_data['title'])
        self.assertContains(response, self.question_data['text'])
        self.assertContains(response, invalid_tag)
        self.assertFalse(Question.objects.exists())
        self.assertFalse(Tag.objects.exists())


class AnswerSubmissionTests(TestCase):
    answer_text = 'Новый ответ на вопрос'

    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.author = users.create_user(username='question-author')
        cls.reader = users.create_user(username='answer-author')
        cls.question = Question.objects.create(title='Вопрос', text='Текст', author=cls.author)
        cls.url = cls.question.get_absolute_url()

    def add_ten_answers(self, created_at):
        Answer.objects.bulk_create([
            Answer(question=self.question, author=self.author, text=f'Ответ {number}', created_at=created_at)
            for number in range(10)
        ])

    def test_guest_can_read_question_and_must_log_in_to_answer(self):
        response = self.client.get(self.url)

        self.assertContains(response, self.question.title)
        self.assertContains(response, '<fieldset disabled')
        self.assertContains(response, 'title="Войдите, чтобы ответить"')
        self.assertRedirects(
            self.client.post(self.url, {'text': self.answer_text}),
            f'/login/?next={self.url}',
        )
        self.assertFalse(Answer.objects.exists())

    def test_post_requires_csrf_and_redirects_to_answer_on_second_page(self):
        self.add_ten_answers(timezone.now() - timedelta(days=1))
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reader)
        data = {'text': self.answer_text}

        self.assertEqual(client.get(self.url).status_code, 200)
        self.assertEqual(client.post(self.url, data).status_code, 403)
        response = client.post(self.url, {
            **data, 'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        }, follow=True)

        answer = Answer.objects.filter(question=self.question, author=self.reader).first()
        self.assertIsNotNone(answer)
        self.assertEqual(answer.text, self.answer_text)
        self.assertRedirects(response, f'{self.url}?page=2#answer-{answer.pk}')
        self.assertContains(response, f'id="answer-{answer.pk}"')
        self.assertContains(response, self.answer_text)

    def test_redirect_uses_the_new_answers_position_even_if_it_is_on_first_page(self):
        self.add_ten_answers(timezone.now() + timedelta(days=1))
        self.client.force_login(self.reader)

        response = self.client.post(f'{self.url}?page=2', {'text': self.answer_text})

        answer = Answer.objects.filter(question=self.question, author=self.reader).first()
        self.assertIsNotNone(answer)
        self.assertRedirects(response, f'{self.url}#answer-{answer.pk}')

    def test_empty_answer_displays_error_and_remains_bound(self):
        self.client.force_login(self.reader)

        response = self.client.post(self.url, {'text': '   '})

        form = response.context.get('form')
        self.assertIsNotNone(form)
        self.assertEqual(form['text'].value(), '   ')
        self.assertTrue(form.has_error('text', 'required'))
        self.assertContains(response, form['text'].errors[0])
        self.assertFalse(Answer.objects.exists())


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

    def test_hot_ranks_questions_by_signed_votes(self):
        for vote in QuestionLike.objects.filter(question=self.old):
            vote.value = -1
            vote.save()

        response = self.client.get(reverse('questions:hot'))

        self.assertEqual(
            [(question.pk, question.rating) for question in response.context['page_obj']],
            [(self.new.pk, 0), (self.old.pk, -2)],
        )

    def test_answer_ratings_sum_likes_and_dislikes(self):
        for answer in (self.first_answer, self.second_answer):
            vote = AnswerLike(answer=answer, user=self.reader)
            vote.value = -1
            vote.save()

        response = self.client.get(self.old.get_absolute_url())

        self.assertEqual([answer.rating for answer in response.context['page_obj']], [0, -1])
        self.assertEqual(response.context['question'].answer_count, 2)

    def test_database_checks_question_and_answer_vote_values(self):
        for vote in (
            QuestionLike(question=self.new, user=self.reader),
            AnswerLike(answer=self.second_answer, user=self.reader),
        ):
            with self.subTest(model=type(vote).__name__):
                vote.value = 0
                with self.assertRaises(IntegrityError), transaction.atomic():
                    vote.save()

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
        self.client.force_login(self.reader)
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
