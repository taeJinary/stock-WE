from django.shortcuts import render

from .models import DailyBriefing


def briefing_list(request):
    briefings = DailyBriefing.objects.all()[:30]
    return render(request, "briefing/list.html", {"briefings": briefings})
