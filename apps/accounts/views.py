from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import SignupForm
from .models import Subscription


@login_required
def profile(request):
    return render(
        request,
        "accounts/profile.html",
        {"subscription": request.user.active_subscription},
    )


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            Subscription.objects.create(
                user=user,
                plan=Subscription.Plan.FREE,
            )
            login(request, user)
            return redirect("dashboard:home")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


def logout_redirect_home(request):
    logout(request)
    return redirect("dashboard:home")
