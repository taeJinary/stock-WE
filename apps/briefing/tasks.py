from celery import chain, shared_task
from django.utils import timezone

from services.briefing_generator import create_daily_briefing
from services.interest_service import collect_interest_snapshot
from services.stock_service import refresh_market_prices


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def sync_market_data_task(self, previous_result=None):
    return refresh_market_prices()


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def sync_interest_data_task(self, previous_result=None):
    return collect_interest_snapshot()


@shared_task(bind=True, max_retries=3, default_retry_delay=600)
def generate_daily_briefing_task(self, previous_result=None):
    today = timezone.localdate()
    briefing = create_daily_briefing(target_date=today)
    return {
        "status": "success",
        "briefing_date": str(briefing.briefing_date),
        "generated_by": briefing.generated_by,
    }


@shared_task
def run_daily_pipeline_task():
    workflow = chain(
        sync_market_data_task.s(),
        sync_interest_data_task.s(),
        generate_daily_briefing_task.s(),
    )
    async_result = workflow.apply_async()
    return {
        "status": "success",
        "task_id": async_result.id,
    }
