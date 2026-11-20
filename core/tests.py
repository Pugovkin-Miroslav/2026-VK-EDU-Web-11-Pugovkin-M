from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse

from .models import Profile


class LoginLogoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.credentials = {'username': 'reader', 'password': 'reader-test-password'}
        cls.user = get_user_model().objects.create_user(
            first_name='Тестовый читатель', **cls.credentials,
        )

    def test_login_requires_csrf_and_returns_to_next_from_the_form(self):
        client = Client(enforce_csrf_checks=True)
        login_url = reverse('core:login')
        next_url = '/hot/?page=2&filter=mine'

        response = client.get(login_url, {'next': next_url})
        self.assertContains(
            response, '<input type="hidden" name="next" value="/hot/?page=2&amp;filter=mine">',
            html=True,
        )
        data = {**self.credentials, 'next': next_url}
        self.assertEqual(client.post(login_url, data).status_code, 403)

        data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        response = client.post(login_url, data)

        self.assertRedirects(response, next_url)
        self.assertEqual(client.get(next_url).wsgi_request.user, self.user)

    def test_login_falls_back_to_home_without_a_safe_next(self):
        for next_url in (None, 'https://example.org/', '//example.org/'):
            with self.subTest(next=next_url):
                data = self.credentials.copy()
                if next_url is not None:
                    data['next'] = next_url
                response = self.client.post(reverse('core:login'), data)

                self.assertRedirects(response, '/')

    def test_invalid_password_displays_error_and_preserves_username(self):
        response = self.client.post(
            reverse('core:login'),
            {'username': self.user.username, 'password': 'incorrect-password'},
        )

        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'value="reader"')
        form_error, = response.context['form'].non_field_errors()
        self.assertContains(response, form_error)
        self.assertNotContains(response, 'incorrect-password')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post_and_csrf_and_returns_to_the_current_page(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        logout_url = '/logout/'
        current_url = '/hot/?page=2&filter=mine'

        response = client.get(current_url)
        self.assertContains(response, '<form method="post" action="/logout/">')
        self.assertContains(
            response, '<input type="hidden" name="next" value="/hot/?page=2&amp;filter=mine">',
            html=True,
        )
        self.assertEqual(client.get(logout_url).status_code, 405)
        self.assertEqual(client.post(logout_url, {'next': current_url}).status_code, 403)
        self.assertTrue(client.get(current_url).wsgi_request.user.is_authenticated)

        response = client.post(logout_url, {
            'next': current_url,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        })

        self.assertRedirects(response, current_url)
        self.assertFalse(client.get(current_url).wsgi_request.user.is_authenticated)

    def test_logout_rejects_external_next(self):
        self.client.force_login(self.user)

        response = self.client.post('/logout/', {'next': 'https://example.org/'})

        self.assertRedirects(response, '/')
        self.assertFalse(self.client.get('/').wsgi_request.user.is_authenticated)

    def test_header_reflects_the_session_even_on_the_ask_page(self):
        for url in ('/', reverse('questions:ask')):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, 'href="/login/"')
                self.assertContains(response, 'href="/signup/"')
                self.assertNotContains(response, 'Выйти')

        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, self.user.first_name)
        self.assertContains(response, 'Выйти')
        self.assertNotContains(response, 'href="/login/"')
        self.assertNotContains(response, 'href="/signup/"')


class SignupTests(TestCase):
    signup_data = {
        'username': 'new-reader',
        'email': 'reader@example.com',
        'first_name': 'Мария',
        'password1': 'Lavender-puzzle-93',
        'password2': 'Lavender-puzzle-93',
    }

    def test_signup_creates_user_and_one_profile_after_csrf_check(self):
        client = Client(enforce_csrf_checks=True)
        url = reverse('core:signup')

        self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.post(url, self.signup_data).status_code, 403)
        self.assertFalse(get_user_model().objects.exists())

        response = client.post(url, {
            **self.signup_data,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        })

        self.assertRedirects(response, '/')
        user = get_user_model().objects.get(username='new-reader')
        self.assertEqual(user.email, 'reader@example.com')
        self.assertEqual(user.first_name, 'Мария')
        self.assertTrue(user.check_password(self.signup_data['password1']))
        self.assertEqual(Profile.objects.get().user, user)

    def test_password_validation_displays_errors_and_preserves_input(self):
        response = self.client.post(reverse('core:signup'), {
            **self.signup_data, 'password1': '123456', 'password2': '123456',
        })

        form = response.context.get('form')
        self.assertIsNotNone(form)
        self.assertTrue(form.has_error('password2', 'password_too_short'))
        self.assertTrue(form.has_error('password2', 'password_entirely_numeric'))
        for error in form['password2'].errors:
            self.assertContains(response, error)
        for value in ('new-reader', 'reader@example.com', 'Мария'):
            self.assertContains(response, f'value="{value}"')
        self.assertNotContains(response, 'value="123456"')
        self.assertFalse(get_user_model().objects.exists())

    def test_signup_requires_email_name_and_matching_passwords(self):
        response = self.client.post(reverse('core:signup'), {
            **self.signup_data, 'email': '', 'first_name': '', 'password2': 'different',
        })

        form = response.context.get('form')
        self.assertIsNotNone(form)
        self.assertTrue(form.has_error('email', 'required'))
        self.assertTrue(form.has_error('first_name', 'required'))
        self.assertTrue(form.has_error('password2', 'password_mismatch'))
        self.assertFalse(get_user_model().objects.exists())

    def test_signup_rejects_a_taken_username(self):
        users = get_user_model().objects
        users.create_user(username='new-reader')

        response = self.client.post(reverse('core:signup'), self.signup_data)

        form = response.context.get('form')
        self.assertIsNotNone(form)
        self.assertTrue(form.has_error('username', 'unique'))
        self.assertEqual(users.count(), 1)
        self.assertFalse(Profile.objects.exists())


class ProfileTests(TestCase):
    def test_user_can_have_only_one_profile(self):
        user = get_user_model().objects.create_user(username='reader')
        profile = Profile.objects.create(user=user)

        self.assertEqual(user.profile, profile)
        self.assertFalse(profile.avatar)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Profile.objects.create(user=user)


class ProfileAdminTests(TestCase):
    def test_admin_displays_profile_inline_on_user_change(self):
        users = get_user_model().objects
        admin_user = users.create_superuser(username='admin')
        user = users.create_user(username='reader')
        Profile.objects.create(user=user)
        self.client.force_login(admin_user)

        response = self.client.get(reverse('admin:auth_user_change', args=[user.pk]))

        self.assertContains(response, 'name="profile-TOTAL_FORMS"')
        self.assertContains(response, '<html lang="ru"')
        inline, = response.context['inline_admin_formsets']
        self.assertIs(inline.formset.model, Profile)
