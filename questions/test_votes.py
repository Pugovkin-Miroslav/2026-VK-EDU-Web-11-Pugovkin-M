from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .models import Answer, AnswerLike, Question, QuestionLike


class VoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.author = users.create_user(username='author')
        cls.reader = users.create_user(username='reader')
        cls.question = Question.objects.create(title='Вопрос', text='Текст', author=cls.author)
        cls.answer = Answer.objects.create(text='Ответ', question=cls.question, author=cls.author)

    def test_vote_updates_ratings_and_rejects_repeated_values(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reader)
        client.get('/')
        headers = {'X-CSRFToken': client.cookies['csrftoken'].value}
        for url, target, votes in (
            ('/ajax/vote/question/', self.question, self.question.likes),
            ('/ajax/vote/answer/', self.answer, self.answer.likes),
        ):
            with self.subTest(url=url):
                votes.create(user=self.author, value=1)
                data = {'id': target.pk, 'value': 1}

                response = client.post(url, data, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'rating': 2, 'value': 1})

                duplicate = client.post(url, data, headers=headers)
                self.assertEqual(duplicate.status_code, 409)
                self.assertTrue(duplicate.json()['error'])

                changed_vote = client.post(url, {**data, 'value': -1}, headers=headers)
                self.assertEqual(changed_vote.status_code, 200)
                self.assertEqual(changed_vote.json(), {'rating': 0, 'value': -1})
                self.assertEqual(votes.get(user=self.reader).value, -1)
                self.assertEqual(votes.count(), 2)

    def test_removing_a_vote_recalculates_rating_and_keeps_other_votes(self):
        self.client.force_login(self.reader)

        for url, target, initial_value in (
            ('/ajax/vote/question/', self.question, 1),
            ('/ajax/vote/answer/', self.answer, -1),
        ):
            with self.subTest(url=url):
                target.likes.create(user=self.author, value=1)
                target.likes.create(user=self.reader, value=initial_value)
                data = {'id': target.pk, 'value': 0}

                for _ in range(2):
                    response = self.client.post(url, data)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), {'rating': 1, 'value': 0})

                self.assertFalse(target.likes.filter(user=self.reader).exists())
                self.assertEqual(target.likes.get().user, self.author)

    def test_invalid_parameters_and_missing_target_return_json_errors(self):
        self.client.force_login(self.reader)
        url = '/ajax/vote/question/'

        for data, status in (
            ({'id': self.question.pk, 'value': 2}, 400),
            ({'id': 'incorrect', 'value': -1}, 400),
            ({'id': 2**63, 'value': -1}, 400),
            ({'id': self.question.pk + 100, 'value': -1}, 404),
        ):
            with self.subTest(data=data):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.headers['Content-Type'], 'application/json')
                self.assertTrue(response.json()['error'])
        self.assertFalse(QuestionLike.objects.exists())

    def test_vote_routes_require_post_authentication_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.get(self.question.get_absolute_url())
        csrf = client.cookies['csrftoken'].value

        for url, target in (
            ('/ajax/vote/question/', self.question), ('/ajax/vote/answer/', self.answer),
        ):
            with self.subTest(url=url):
                method_error = client.get(url)
                self.assertEqual(method_error.status_code, 405)
                self.assertEqual(method_error.headers['Allow'], 'POST')
                self.assertTrue(method_error.json()['error'])

                data = {'id': target.pk, 'value': 1}
                forbidden = client.post(url, data)
                self.assertEqual(forbidden.status_code, 403)
                self.assertTrue(forbidden.json()['error'])

                unauthorized = client.post(url, data, HTTP_X_CSRFTOKEN=csrf)
                self.assertEqual(unauthorized.status_code, 401)
                self.assertTrue(unauthorized.json()['error'])

        login_response = client.post('/login/', {})
        self.assertEqual(login_response.status_code, 403)
        self.assertTrue(login_response.headers['Content-Type'].startswith('text/html'))
        self.assertFalse(QuestionLike.objects.exists())
        self.assertFalse(AnswerLike.objects.exists())

    def test_guest_buttons_are_disabled_and_signed_in_user_sees_selected_votes(self):
        QuestionLike.objects.create(question=self.question, user=self.reader, value=1)
        AnswerLike.objects.create(answer=self.answer, user=self.reader, value=-1)

        homepage = self.client.get('/')
        self.assertContains(homepage, 'title="Войдите, чтобы голосовать"')
        for value in (1, -1):
            self.assertRegex(
                homepage.content.decode(), rf'<button[^>]+value="{value}"[^>]+disabled',
            )

        self.client.force_login(self.reader)
        homepage = self.client.get('/')
        detail = self.client.get(self.question.get_absolute_url())

        self.assertContains(homepage, 'action="/ajax/vote/question/"')
        self.assertContains(detail, 'action="/ajax/vote/answer/"')
        self.assertRegex(
            homepage.content.decode(), r'<button[^>]+value="1"[^>]+aria-pressed="true"\s+title="[^"]+">',
        )
        self.assertRegex(
            detail.content.decode(), r'<button[^>]+value="-1"[^>]+aria-pressed="true"\s+title="[^"]+">',
        )
