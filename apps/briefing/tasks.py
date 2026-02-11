import logging
from datetime import date

from celery import chain, shared_task
from django.utils import timezone

from apps.briefing.models import DailyBriefing
from services.briefing_delivery_service import send_daily_briefing_email
from services.briefing_generator import create_daily_briefing
from services.interest_service import collect_interest_snapshot
from services.news_service import collect_news_items
from services.stock_service import refresh_market_prices

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def sync_market_data_task(self, previous_result=None):
    result = refresh_market_prices()
    if result.get("status") == "partial":
        failed = result.get("failed", [])
        if failed:
            logger.warning("Market sync partial: %s", failed)
        all_failed = bool(failed) and not (
            result.get("inserted") or result.get("updated") or result.get("skipped")
        )
        has_retryable_failure = any(
            item.get("reason") in {"API_ERROR", "RATE_LIMIT"} for item in failed
        )
        if all_failed and has_retryable_failure and self.request.retries < self.max_retries:
            raise self.retry(exc=RuntimeError("Market sync failed by external API"))
    return result


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def sync_interest_data_task(self, previous_result=None):
    result = collect_interest_snapshot()
    if result.get("status") == "error":
        if self.request.retries < self.max_retries:
            raise self.retry(exc=RuntimeError(result.get("message", "interest sync error")))
    if result.get("status") == "partial":
        logger.warning("Interest sync partial: %s", result)
    return result


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def sync_news_data_task(self, previous_result=None):
    result = collect_news_items()
    if result.get("status") == "error":
        if self.request.retries < self.max_retries:
            raise self.retry(exc=RuntimeError(result.get("message", "news sync error")))
    if result.get("status") == "partial":
        logger.warning("News sync partial: %s", result)
    return result


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def generate_daily_briefing_task(self, previous_result=None):
    today = timezone.localdate()
    briefing = create_daily_briefing(target_date=today)
    if briefing.generated_by == "gemini-fallback":
        logger.warning("Briefing fallback generated on %s", today)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=RuntimeError("Gemini fallback result"))
        return {
            "status": "partial",
            "briefing_date": str(briefing.briefing_date),
            "generated_by": briefing.generated_by,
        }

    return {
        "status": "success",
        "briefing_date": str(briefing.briefing_date),
        "generated_by": briefing.generated_by,
    }


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def send_daily_briefing_email_task(self, previous_result=None):
    briefing_date = timezone.localdate()
    if isinstance(previous_result, dict) and previous_result.get("briefing_date"):
        try:
            briefing_date = date.fromisoformat(previous_result["briefing_date"])
        except ValueError:
            briefing_date = timezone.localdate()

    result = send_daily_briefing_email(briefing_date=briefing_date)
    if result.get("status") == "error":
        if self.request.retries < self.max_retries:
            raise self.retry(exc=RuntimeError(result.get("message", "email delivery error")))
    if result.get("status") == "partial":
        logger.warning("Briefing email delivery partial: %s", result)

    email_status = result.get("email_status")
    if email_status == DailyBriefing.EmailStatus.FAILED and self.request.retries < self.max_retries:
        raise self.retry(exc=RuntimeError("All briefing email deliveries failed"))

    return result


@shared_task
def run_daily_pipeline_task():
    workflow = chain(
        sync_market_data_task.s(),
        sync_news_data_task.s(),
        sync_interest_data_task.s(),
        generate_daily_briefing_task.s(),
        send_daily_briefing_email_task.s(),
    )
    async_result = workflow.apply_async()
    return {
        "status": "success",
        "task_id": async_result.id,
    }
