from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Watchlist


@login_required
def watchlist_list(request):
    watchlists = (
        Watchlist.objects.filter(user=request.user)
        .prefetch_related("items__stock")
        .all()
    )
    return render(request, "watchlist/list.html", {"watchlists": watchlists})
