from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import Profile


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
