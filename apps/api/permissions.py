from rest_framework.permissions import BasePermission

from apps.accounts.models import Subscription
from services.watchlist_service import get_user_plan


class HasApiPlanPermission(BasePermission):
    message = "PRO or ENTERPRISE subscription is required for API access."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True

        plan = get_user_plan(user)
        return plan in {Subscription.Plan.PRO, Subscription.Plan.ENTERPRISE}
