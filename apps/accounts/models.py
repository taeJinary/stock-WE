from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Region(models.TextChoices):
        KOREA = "KR", "Korea"
        USA = "US", "USA"
        GLOBAL = "GL", "Global"

    region = models.CharField(
        max_length=2,
        choices=Region.choices,
        default=Region.GLOBAL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def active_subscription(self):
        today = timezone.localdate()
        return self.subscriptions.filter(
            is_active=True,
            start_date__lte=today,
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=today)
        ).order_by("-start_date").first()


class Subscription(models.Model):
    class Plan(models.TextChoices):
        FREE = "free", "Free"
        PRO = "pro", "Pro"
        ENTERPRISE = "enterprise", "Enterprise"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="subscriptions",
        on_delete=models.CASCADE,
    )
    plan = models.CharField(max_length=16, choices=Plan.choices, default=Plan.FREE)
    is_trial = models.BooleanField(default=False)
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date", "-id"]

    def clean(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("end_date cannot be earlier than start_date")

    def __str__(self):
        return f"{self.user.username} / {self.plan}"
