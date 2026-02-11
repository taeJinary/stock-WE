from django.db import models


class DailyBriefing(models.Model):
    class EmailStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    briefing_date = models.DateField(unique=True)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    discussed_symbols = models.JSONField(default=list, blank=True)
    generated_by = models.CharField(max_length=32, default="gemini")
    email_status = models.CharField(
        max_length=16,
        choices=EmailStatus.choices,
        default=EmailStatus.PENDING,
    )
    email_sent_count = models.PositiveIntegerField(default=0)
    email_target_count = models.PositiveIntegerField(default=0)
    email_sent_at = models.DateTimeField(blank=True, null=True)
    email_failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-briefing_date", "-id"]

    def __str__(self):
        return f"{self.briefing_date} / {self.title}"
