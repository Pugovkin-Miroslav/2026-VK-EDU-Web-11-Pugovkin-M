from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

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

    def test_header_reflects_the_session_on_public_pages(self):
        for url in ('/', reverse('questions:ask')):
            with self.subTest(url=url):
                response = self.client.get(url, follow=True)
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

    def test_signup_creates_user_and_profile_and_starts_session(self):
        client = Client(enforce_csrf_checks=True)
        url = reverse('core:signup')

        self.assertEqual(client.get(url).status_code, 200)
        self.assertEqual(client.post(url, self.signup_data).status_code, 403)
        self.assertFalse(get_user_model().objects.exists())

        response = client.post(url, {
            **self.signup_data,
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        }, follow=True)

        self.assertRedirects(response, '/')
        user = get_user_model().objects.get(username='new-reader')
        self.assertEqual(user.email, 'reader@example.com')
        self.assertEqual(user.first_name, 'Мария')
        self.assertTrue(user.check_password(self.signup_data['password1']))
        self.assertEqual(Profile.objects.get().user, user)
        self.assertEqual(response.wsgi_request.user, user)

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


class ProfileEditingTests(TestCase):
    profile_data = {'email': 'updated@example.com', 'nick': 'Новое имя'}

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='reader', email='reader@example.com', first_name='Читатель',
        )

    def setUp(self):
        self.url = reverse('core:profile')
        self.media_root = self.enterContext(TemporaryDirectory())
        self.enterContext(self.settings(MEDIA_ROOT=self.media_root, MEDIA_URL='/user-media/'))
        self.client.force_login(self.user)

    @staticmethod
    def avatar_upload(filename='portrait.png', padding=0):
        with BytesIO() as data:
            Image.new('RGB', (2, 2)).save(data, format='PNG')
            return SimpleUploadedFile(filename, data.getvalue() + b'\0' * padding)

    def test_profile_requires_login_for_get_and_post(self):
        guest = Client()

        self.assertRedirects(guest.get(self.url), '/login/?next=/profile/')
        self.assertRedirects(guest.post(self.url, self.profile_data), '/login/?next=/profile/')

    def test_profile_shows_current_values_and_default_avatar(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'value="reader@example.com"')
        self.assertContains(response, 'value="Читатель"')
        self.assertContains(response, 'src="/static/core/img/profile-icon.png"')
        self.assertContains(response, 'data-avatar-max-bytes="2097152"')
        self.assertContains(response, 'src="/static/core/js/profile.js"')
        self.assertFalse(Profile.objects.filter(user=self.user).exists())

    def test_save_updates_profile_and_displays_uploaded_avatar(self):
        response = self.client.post(self.url, {
            **self.profile_data, 'avatar': self.avatar_upload(),
        })

        self.assertRedirects(response, self.url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated@example.com')
        self.assertEqual(self.user.first_name, 'Новое имя')
        self.assertEqual(self.user.username, 'reader')
        avatar = Profile.objects.get(user=self.user).avatar
        self.assertRegex(avatar.name, r'^avatars/[0-9a-f]{32}\.png$')
        self.assertTrue(Path(self.media_root, avatar.name).is_file())
        self.assertContains(self.client.get(self.url), f'src="{avatar.url}"')
        self.assertContains(self.client.get('/'), f'src="/user-media/{avatar.name}"')

    def test_saving_without_a_file_keeps_the_existing_avatar(self):
        Profile.objects.create(user=self.user, avatar='avatars/old.png')

        response = self.client.post(self.url, self.profile_data)

        self.assertRedirects(response, self.url)
        self.assertEqual(Profile.objects.get(user=self.user).avatar.name, 'avatars/old.png')

    def test_invalid_avatars_display_errors_without_saving_profile_changes(self):
        for avatar, code in (
            (self.avatar_upload('portrait.gif'), 'invalid_extension'),
            (self.avatar_upload('portrait.jpg'), 'invalid_image_format'),
            (self.avatar_upload(padding=2 * 1024 * 1024), 'file_too_large'),
            (SimpleUploadedFile('portrait.png', b'not an image'), 'invalid_image'),
        ):
            with self.subTest(code=code):
                response = self.client.post(self.url, {**self.profile_data, 'avatar': avatar})

                form = response.context.get('form')
                self.assertIsNotNone(form)
                self.assertTrue(form.has_error('avatar', code))
                self.assertContains(response, form['avatar'].errors[0])
                self.assertContains(response, 'value="updated@example.com"')
                self.assertContains(response, 'value="Новое имя"')

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'reader@example.com')
        self.assertFalse(Profile.objects.filter(user=self.user).exists())


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
