from django.urls import reverse
from django.test.utils import override_settings
from unittest.mock import patch

from rest_framework.test import APITestCase

from mresponse.moderations.tests.factories import ModerationFactory
from mresponse.responses.tests.factories import ResponseFactory
from mresponse.users.tests.factories import (
    BypassStaffModerationUserFactory,
    UserFactory,
)


@override_settings(PLAY_STORE_SUBMIT_REPLY_ENABLED=True)
@patch("mresponse.responses.models.reply_to_review")
class TestCreateModerationApi(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_create_moderation(self, mock_reply_to_review):
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )
        self.assertEqual(result.status_code, 201)
        mock_reply_to_review.assert_not_called()
        response.refresh_from_db()
        self.assertFalse(response.approved)
        self.assertFalse(response.staff_approved)
        self.assertFalse(response.submitted_to_play_store)

    def test_create_moderation_if_user_is_author(self, mock_reply_to_review):
        response = ResponseFactory(approved=False, author=self.user)
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )
        self.assertEqual(result.status_code, 400)
        mock_reply_to_review.assert_not_called()

    def test_is_approved_after_moderation(self, mock_reply_to_review):
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )
        self.assertEqual(result.status_code, 201)

        user = UserFactory(username="test1")
        self.client.force_login(user)
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )
        self.assertEqual(result.status_code, 201)

        user = UserFactory(username="test2")
        self.client.force_login(user)
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )

        self.assertEqual(result.status_code, 201)
        mock_reply_to_review.assert_not_called()

        response.refresh_from_db()
        self.assertTrue(response.approved)
        self.assertFalse(response.staff_approved)
        self.assertFalse(response.submitted_to_play_store)

    def test_is_staff_approved_after_moderation_by_mod_two(self, mock_reply_to_review):
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))

        self.client.force_login(BypassStaffModerationUserFactory())
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )

        self.assertEqual(result.status_code, 201)
        mock_reply_to_review.assert_called()

        response.refresh_from_db()
        self.assertTrue(response.approved)
        self.assertTrue(response.staff_approved)
        self.assertTrue(response.submitted_to_play_store)

    def test_is_staff_approved_after_partial_approval_by_mod_two(
        self, mock_reply_to_review
    ):
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))
        ModerationFactory(response=response)
        ModerationFactory(response=response)

        self.client.force_login(BypassStaffModerationUserFactory())
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(
                positive_in_tone=True, addressing_the_issue=False, personal=False
            ),
        )

        self.assertEqual(result.status_code, 201)
        mock_reply_to_review.assert_called()

        response.refresh_from_db()
        self.assertTrue(response.approved)
        self.assertTrue(response.staff_approved)
        self.assertTrue(response.submitted_to_play_store)

    @patch("mresponse.moderations.api.views.user_can_bypass_staff_approval_for_review")
    def test_isnt_staff_approved_after_moderation_by_mod_two_without_locale(
        self, mock_moderator_in_review_langauge, mock_reply_to_review
    ):
        mock_moderator_in_review_langauge.return_value = False
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))

        self.client.force_login(BypassStaffModerationUserFactory())
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )

        self.assertEqual(result.status_code, 201)
        mock_reply_to_review.assert_not_called()

        response.refresh_from_db()
        self.assertTrue(response.approved)
        self.assertFalse(response.staff_approved)
        self.assertFalse(response.submitted_to_play_store)


class TestModerationKarmaPointsApi(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)

    def test_first_moderation(self):
        self.assertEqual(self.user.profile.karma_points, 0)
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))
        self.assertEqual(response.moderation_count(), 0)
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )
        self.assertEqual(result.status_code, 201)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.karma_points, 1)

    def test_second_moderation(self):
        self.assertEqual(self.user.profile.karma_points, 0)
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))
        ModerationFactory(response=response)
        self.assertEqual(response.moderation_count(), 1)
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )
        self.assertEqual(result.status_code, 201)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.karma_points, 2)

    def test_third_moderation(self):
        self.assertEqual(self.user.profile.karma_points, 0)
        response = ResponseFactory(approved=False, author=UserFactory(username="smith"))
        ModerationFactory(response=response)
        ModerationFactory(response=response)
        self.assertEqual(response.moderation_count(), 2)
        result = self.client.post(
            reverse("create_moderation", kwargs={"response_pk": response.pk}),
            data=dict(positive_in_tone=True, addressing_the_issue=True, personal=True),
        )
        self.assertEqual(result.status_code, 201)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.karma_points, 3)
        response.author.profile.refresh_from_db()
        self.assertEqual(response.author.profile.karma_points, 1)
