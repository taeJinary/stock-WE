from django.contrib import admin

from .models import DailyBriefing


@admin.register(DailyBriefing)
class DailyBriefingAdmin(admin.ModelAdmin):
    list_display = (
        "briefing_date",
        "title",
        "generated_by",
        "email_status",
        "email_recipient_count",
        "email_sent_at",
        "created_at",
    )
    search_fields = ("title", "summary")
    list_filter = ("generated_by", "email_status", "briefing_date")
