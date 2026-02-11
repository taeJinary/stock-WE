from typing import Optional

from apps.accounts.models import Subscription
from apps.watchlist.models import Watchlist

FREE_WATCHLIST_LIMIT = 3
DEFAULT_WATCHLIST_NAME = "My Watchlist"


def get_user_plan(user) -> str:
    subscription = getattr(user, "active_subscription", None)
    if not subscription:
        return Subscription.Plan.FREE
    return subscription.plan


def get_watchlist_limit(user) -> Optional[int]:
    plan = get_user_plan(user)
    if plan in {Subscription.Plan.PRO, Subscription.Plan.ENTERPRISE}:
        return None
    return FREE_WATCHLIST_LIMIT


def can_user_create_watchlist(user) -> tuple[bool, Optional[int]]:
    limit = get_watchlist_limit(user)
    if limit is None:
        return True, None

    current_count = Watchlist.objects.filter(user=user).count()
    return current_count < limit, limit


def ensure_default_watchlist(user) -> Watchlist:
    default_watchlist = Watchlist.objects.filter(user=user, is_default=True).first()
    if default_watchlist:
        return default_watchlist

    first_watchlist = Watchlist.objects.filter(user=user).order_by("id").first()
    if first_watchlist:
        first_watchlist.is_default = True
        first_watchlist.save(update_fields=["is_default"])
        return first_watchlist

    can_create, limit = can_user_create_watchlist(user)
    if not can_create:
        if limit is None:
            raise ValueError("Cannot create default watchlist")
        raise ValueError(f"Watchlist limit reached ({limit})")

    return Watchlist.objects.create(
        user=user,
        name=DEFAULT_WATCHLIST_NAME,
        is_default=True,
    )
