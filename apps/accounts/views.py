from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.accounts.forms import SignupForm
from apps.accounts.models import Subscription


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            if not user.subscriptions.exists():
                Subscription.objects.create(
                    user=user,
                    plan=Subscription.Plan.FREE,
                    is_active=True,
                )
            login(request, user)
            messages.success(request, "회원가입이 완료되었습니다.")
            return redirect("dashboard:home")
    else:
        form = SignupForm()

    return render(request, "accounts/signup.html", {"form": form})


@login_required
def profile(request):
    return render(
        request,
        "accounts/profile.html",
        {"subscription": request.user.active_subscription},
    )
