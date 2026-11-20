from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Profile


class ProfileTests(TestCase):
    def test_user_can_have_only_one_profile(self):
        user = get_user_model().objects.create_user(username='reader')
        profile = Profile.objects.create(user=user)

        self.assertEqual(user.profile, profile)
        self.assertFalse(profile.avatar)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Profile.objects.create(user=user)
