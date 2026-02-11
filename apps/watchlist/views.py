from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.stocks.models import Stock
from services.watchlist_service import (
    can_user_create_watchlist,
    ensure_default_watchlist,
    get_watchlist_limit,
)

from .models import Watchlist, WatchlistItem


def _get_next_url(request, fallback_url):
    next_url = request.POST.get("next", "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


@login_required
def watchlist_list(request):
    watchlists = (
        Watchlist.objects.filter(user=request.user)
        .prefetch_related("items__stock")
        .all()
    )
    watchlist_limit = get_watchlist_limit(request.user)
    return render(
        request,
        "watchlist/list.html",
        {
            "watchlists": watchlists,
            "watchlist_limit": watchlist_limit,
        },
    )


@login_required
@require_POST
def watchlist_create(request):
    name = request.POST.get("name", "").strip()
    redirect_url = _get_next_url(request, reverse("watchlist:list"))

    if not name:
        messages.error(request, "Watchlist name is required.")
        return redirect(redirect_url)

    if len(name) > 120:
        messages.error(request, "Watchlist name must be 120 characters or less.")
        return redirect(redirect_url)

    can_create, limit = can_user_create_watchlist(request.user)
    if not can_create:
        if limit is None:
            messages.error(request, "Unable to create watchlist.")
        else:
            messages.error(request, f"Free plan can have up to {limit} watchlists.")
        return redirect(redirect_url)

    is_default = not Watchlist.objects.filter(user=request.user).exists()
    try:
        watchlist, created = Watchlist.objects.get_or_create(
            user=request.user,
            name=name,
            defaults={"is_default": is_default},
        )
    except IntegrityError:
        messages.error(request, "Watchlist could not be created. Please try another name.")
        return redirect(redirect_url)

    if created:
        messages.success(request, f"Watchlist '{watchlist.name}' created.")
    else:
        messages.info(request, f"Watchlist '{watchlist.name}' already exists.")
    return redirect(redirect_url)


@login_required
@require_POST
def watchlist_delete(request, watchlist_id):
    redirect_url = _get_next_url(request, reverse("watchlist:list"))
    watchlist = get_object_or_404(Watchlist, id=watchlist_id, user=request.user)
    deleted_name = watchlist.name
    was_default = watchlist.is_default
    watchlist.delete()

    if was_default:
        replacement = Watchlist.objects.filter(user=request.user).order_by("id").first()
        if replacement:
            replacement.is_default = True
            replacement.save(update_fields=["is_default"])

    messages.success(request, f"Watchlist '{deleted_name}' deleted.")
    return redirect(redirect_url)


@login_required
@require_POST
def watchlist_add_item(request, symbol):
    stock = get_object_or_404(Stock, symbol=symbol.upper())
    watchlist_id = request.POST.get("watchlist_id", "").strip()
    note = request.POST.get("note", "").strip()[:255]
    redirect_url = _get_next_url(
        request,
        reverse("stocks:detail", kwargs={"symbol": stock.symbol}),
    )

    if watchlist_id:
        watchlist = get_object_or_404(Watchlist, id=watchlist_id, user=request.user)
    else:
        try:
            watchlist = ensure_default_watchlist(request.user)
        except ValueError:
            messages.error(request, "Unable to resolve watchlist for this account.")
            return redirect(redirect_url)

    item, created = WatchlistItem.objects.get_or_create(
        watchlist=watchlist,
        stock=stock,
        defaults={"note": note},
    )

    if created:
        messages.success(request, f"{stock.symbol} added to '{watchlist.name}'.")
        return redirect(redirect_url)

    if note and note != item.note:
        item.note = note
        item.save(update_fields=["note"])
        messages.success(request, f"Updated note for {stock.symbol} in '{watchlist.name}'.")
    else:
        messages.info(request, f"{stock.symbol} is already in '{watchlist.name}'.")
    return redirect(redirect_url)


@login_required
@require_POST
def watchlist_remove_item(request, symbol):
    stock = get_object_or_404(Stock, symbol=symbol.upper())
    watchlist_id = request.POST.get("watchlist_id", "").strip()
    redirect_url = _get_next_url(request, reverse("watchlist:list"))

    if not watchlist_id:
        messages.error(request, "watchlist_id is required.")
        return redirect(redirect_url)

    deleted_count, _ = WatchlistItem.objects.filter(
        watchlist_id=watchlist_id,
        watchlist__user=request.user,
        stock=stock,
    ).delete()
    if deleted_count:
        messages.success(request, f"{stock.symbol} removed from watchlist.")
    else:
        messages.info(request, f"{stock.symbol} was not in selected watchlist.")
    return redirect(redirect_url)
