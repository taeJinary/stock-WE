from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Subscription, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Profile", {"fields": ("region",)}),
    )
    list_display = ("username", "email", "is_staff", "region", "is_active")
    list_filter = ("is_staff", "is_active", "region")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "is_trial", "start_date", "end_date", "is_active")
    list_filter = ("plan", "is_trial", "is_active")
    search_fields = ("user__username", "user__email")
