import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from apps.briefing.models import DailyBriefing

logger = logging.getLogger(__name__)


def _active_recipient_emails(target_date):
    User = get_user_model()
    return list(
        User.objects.filter(
            is_active=True,
            subscriptions__is_active=True,
            subscriptions__start_date__lte=target_date,
        )
        .filter(
            Q(subscriptions__end_date__isnull=True) | Q(subscriptions__end_date__gte=target_date)
        )
        .exclude(email__isnull=True)
        .exclude(email__exact="")
        .values_list("email", flat=True)
        .distinct()
    )


def _build_email_message(briefing):
    discussed_symbols = briefing.discussed_symbols or []
    symbol_line = ", ".join(discussed_symbols) if discussed_symbols else "-"
    subject = f"[WEStock] {briefing.briefing_date} Morning Briefing"
    message = (
        f"{briefing.title}\n\n"
        f"{briefing.summary}\n\n"
        f"Most Discussed Symbols: {symbol_line}\n"
        "Powered by WEStock"
    )
    return subject, message


def send_daily_briefing_email(briefing_date=None, force=False) -> dict[str, Any]:
    target_date = briefing_date or timezone.localdate()
    try:
        briefing = DailyBriefing.objects.get(briefing_date=target_date)
    except DailyBriefing.DoesNotExist:
        return {
            "status": "error",
            "code": "BRIEFING_NOT_FOUND",
            "message": f"No briefing exists for {target_date}",
        }

    if briefing.email_status == DailyBriefing.EmailStatus.SENT and not force:
        return {
            "status": "skipped",
            "reason": "ALREADY_SENT",
            "briefing_date": str(target_date),
            "sent_count": briefing.email_sent_count,
            "target_count": briefing.email_target_count,
        }

    recipients = _active_recipient_emails(target_date=target_date)
    if not recipients:
        briefing.email_status = DailyBriefing.EmailStatus.SKIPPED
        briefing.email_sent_count = 0
        briefing.email_target_count = 0
        briefing.email_sent_at = None
        briefing.email_failure_reason = "NO_ACTIVE_RECIPIENTS"
        briefing.save(
            update_fields=[
                "email_status",
                "email_sent_count",
                "email_target_count",
                "email_sent_at",
                "email_failure_reason",
                "updated_at",
            ]
        )
        return {
            "status": "skipped",
            "reason": "NO_ACTIVE_RECIPIENTS",
            "briefing_date": str(target_date),
            "sent_count": 0,
            "target_count": 0,
        }

    subject, message = _build_email_message(briefing)
    sent_count = 0
    failures = []
    for email in recipients:
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            sent_count += 1
        except Exception as exc:  # pragma: no cover
            failures.append({"email": email, "error": str(exc)})
            logger.error("Briefing email send failed: %s", exc)

    if sent_count == len(recipients):
        email_status = DailyBriefing.EmailStatus.SENT
    elif sent_count == 0:
        email_status = DailyBriefing.EmailStatus.FAILED
    else:
        email_status = DailyBriefing.EmailStatus.PARTIAL

    failure_message = ""
    if failures:
        failure_message = "; ".join(
            f"{item['email']}: {item['error']}" for item in failures[:3]
        )[:255]

    briefing.email_status = email_status
    briefing.email_sent_count = sent_count
    briefing.email_target_count = len(recipients)
    briefing.email_sent_at = timezone.now() if sent_count > 0 else None
    briefing.email_failure_reason = failure_message
    briefing.save(
        update_fields=[
            "email_status",
            "email_sent_count",
            "email_target_count",
            "email_sent_at",
            "email_failure_reason",
            "updated_at",
        ]
    )

    result_status = "success" if email_status == DailyBriefing.EmailStatus.SENT else "partial"
    if email_status == DailyBriefing.EmailStatus.FAILED:
        result_status = "error"
    return {
        "status": result_status,
        "briefing_date": str(target_date),
        "sent_count": sent_count,
        "target_count": len(recipients),
        "failures": failures[:5],
        "email_status": email_status,
    }
