from django.db import models


class DashboardSnapshot(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dashboard Snapshot"
        verbose_name_plural = "Dashboard Snapshots"
