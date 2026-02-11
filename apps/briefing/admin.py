from django.contrib import admin

from .models import DailyBriefing


@admin.register(DailyBriefing)
class DailyBriefingAdmin(admin.ModelAdmin):
    list_display = ("briefing_date", "title", "generated_by", "created_at")
    search_fields = ("title", "summary")
    list_filter = ("generated_by", "briefing_date")
