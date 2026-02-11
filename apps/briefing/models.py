from django.db import models


class DailyBriefing(models.Model):
    briefing_date = models.DateField(unique=True)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    discussed_symbols = models.JSONField(default=list, blank=True)
    generated_by = models.CharField(max_length=32, default="gemini")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-briefing_date", "-id"]

    def __str__(self):
        return f"{self.briefing_date} / {self.title}"
