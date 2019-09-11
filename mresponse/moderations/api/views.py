from django.db import models, transaction

from rest_framework import generics, permissions, response, status, views

from mresponse.moderations.api import serializers as moderations_serializers
from mresponse.moderations.models import Approval
from mresponse.responses.api.permissions import \
    BypassStaffOrCommunityModerationPermission
from mresponse.responses.models import Response

MODERATION_KARMA_POINTS_AMOUNT = 1


class ModerationMixin:
    def get_response_for_user(self):
        """
        Get a response that matches the ID in the URL and has been
        assigned to the current user.
        """
        # assignment = generics.get_object_or_404(
        #     responses_models.ResponseAssignedToUser.objects.not_expired(),
        #     user=self.request.user,
        #     response_id=self.kwargs['response_pk']
        # )
        # return assignment.response

        return Response.objects.annotate_moderations_count().get(pk=self.kwargs['response_pk'], moderations_count__lt=3)


class CreateModeration(ModerationMixin, generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = moderations_serializers.ModerationSerializer

    def get_queryset(self):
        return Response.objects.exclude(moderations__moderator=self.request.user)

    @transaction.atomic
    def perform_create(self, serializer):
        response = self.get_response_for_user()

        serializer.save(
            response=response,
            moderator=self.request.user,
        )

        # Clear the assignment to the user.
        # self.request.user.response_assignment.delete()

        # Give moderator karma points.
        moderator_profile = self.request.user.profile
        moderator_profile.karma_points = (
            models.F('karma_points') + MODERATION_KARMA_POINTS_AMOUNT
        )
        moderator_profile.save(update_fields=('karma_points',))


class ApproveResponse(ModerationMixin, views.APIView):
    permission_classes = (
        permissions.IsAuthenticated,
        BypassStaffOrCommunityModerationPermission,
    )

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        assigned_response = self.get_response_for_user()

        approval_type = Approval.COMMUNITY

        if request.user.has_perm('responses.can_bypass_staff_moderation'):
            approval_type = Approval.STAFF
            assigned_response.staff_approved = True

        assigned_response.approved = True
        assigned_response.save(update_fields=['staff_approved', 'approved'])

        # Create approval record
        Approval.objects.create(
            response=assigned_response,
            approval_type=approval_type,
            approver=self.request.user
        )

        # Delete user's assignment to this response.
        self.request.user.response_assignment.delete()

        # Give approver a karma point
        moderator_profile = self.request.user.profile
        moderator_profile.karma_points = (
            models.F('karma_points') + MODERATION_KARMA_POINTS_AMOUNT
        )
        moderator_profile.save(update_fields=('karma_points',))

        # Return empty response.
        return response.Response({
            'detail': 'Response approved successfully'
        }, status=status.HTTP_200_OK)
