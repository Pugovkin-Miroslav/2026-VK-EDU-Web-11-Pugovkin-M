from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase

from .models import Answer, Question


class CorrectAnswerTests(TestCase):
    url = '/ajax/answer/correct/'

    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.author = users.create_user(username='question-author')
        cls.reader = users.create_user(username='answer-author')
        cls.question = Question.objects.create(title='Вопрос', text='Текст', author=cls.author)
        cls.first = Answer.objects.create(question=cls.question, author=cls.reader, text='Первый')
        cls.second = Answer.objects.create(question=cls.question, author=cls.reader, text='Второй')

    def test_author_can_select_and_replace_one_correct_answer(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.author)
        client.get(self.question.get_absolute_url())
        headers = {'X-CSRFToken': client.cookies['csrftoken'].value}

        for answer in (self.first, self.second):
            with self.subTest(answer=answer.pk):
                response = client.post(self.url, {
                    'question_id': self.question.pk, 'answer_id': answer.pk,
                }, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'answer_id': answer.pk})
                self.assertEqual(self.question.answers.get(is_correct=True), answer)

        repeated = client.post(self.url, {
            'question_id': self.question.pk, 'answer_id': self.second.pk,
        }, headers=headers)
        self.assertEqual(repeated.status_code, 409)
        self.assertTrue(repeated.json()['error'])

    def test_endpoint_requires_post_authentication_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.question.get_absolute_url())
        data = {'question_id': self.question.pk, 'answer_id': self.first.pk}

        invalid_method = client.get(self.url)
        self.assertEqual(invalid_method.status_code, 405)
        self.assertEqual(invalid_method.headers['Allow'], 'POST')
        self.assertTrue(invalid_method.json()['error'])

        forbidden = client.post(self.url, data)
        self.assertEqual(forbidden.status_code, 403)
        self.assertTrue(forbidden.json()['error'])

        unauthorized = client.post(self.url, data, headers={'X-CSRFToken': client.cookies['csrftoken'].value})
        self.assertEqual(unauthorized.status_code, 401)
        self.assertTrue(unauthorized.json()['error'])
        self.assertFalse(self.question.answers.filter(is_correct=True).exists())

    def test_rejects_wrong_author_and_invalid_targets(self):
        self.client.force_login(self.reader)
        data = {'question_id': self.question.pk, 'answer_id': self.first.pk}
        forbidden = self.client.post(self.url, data)
        self.assertEqual(forbidden.status_code, 403)
        self.assertTrue(forbidden.json()['error'])

        self.client.force_login(self.author)
        other_question = Question.objects.create(title='Другой', text='Текст', author=self.author)
        self.second.is_correct = True
        self.second.save(update_fields=['is_correct'])

        for payload, status in (
            ({**data, 'question_id': other_question.pk}, 404),
            ({**data, 'question_id': 2**63 - 1}, 404),
            ({**data, 'answer_id': 'invalid'}, 400),
            ({**data, 'answer_id': 2**63}, 400),
        ):
            with self.subTest(data=payload):
                response = self.client.post(self.url, payload)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers['Content-Type'], 'application/json')
                self.assertTrue(response.json()['error'])
        self.assertEqual(self.question.answers.get(is_correct=True), self.second)

    def test_selection_controls_are_visible_only_to_the_question_author(self):
        self.first.is_correct = True
        self.first.save(update_fields=['is_correct'])
        question_url = self.question.get_absolute_url()

        guest = self.client.get(question_url)
        self.assertContains(guest, 'Правильный ответ', count=1)
        self.assertNotContains(guest, 'Отметить правильным')

        self.client.force_login(self.reader)
        reader = self.client.get(question_url)
        self.assertContains(reader, 'Правильный ответ', count=1)
        self.assertNotContains(reader, 'Отметить правильным')

        self.client.force_login(self.author)
        author = self.client.get(question_url)
        self.assertContains(author, f'action="{self.url}"', count=2)
        self.assertContains(author, 'data-correct-label', count=1)
        self.assertRegex(author.content.decode(), r'<form[^>]+data-correct-form[^>]+\bhidden>')

    def test_author_page_has_no_badge_when_no_answer_is_correct(self):
        self.client.force_login(self.author)

        response = self.client.get(self.question.get_absolute_url())

        self.assertNotContains(response, 'data-correct-label')

    def test_database_rejects_two_correct_answers_to_one_question(self):
        self.first.is_correct = True
        self.first.save(update_fields=['is_correct'])

        self.second.is_correct = True
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.second.save(update_fields=['is_correct'])
