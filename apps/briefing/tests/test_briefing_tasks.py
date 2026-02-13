from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.briefing.models import DailyBriefing
from apps.briefing.tasks import (
    generate_daily_briefing_task,
    run_daily_pipeline_task,
    send_daily_briefing_email_task,
    sync_interest_data_task,
    sync_market_data_task,
    sync_news_data_task,
)


class BriefingTasksTests(SimpleTestCase):
    @patch(
        "apps.briefing.tasks.refresh_market_prices",
        return_value={
            "status": "partial",
            "failed": [{"reason": "API_ERROR"}],
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        },
    )
    def test_sync_market_data_task_retries_on_retryable_total_failure(self, _mock_refresh):
        with patch(
            "apps.briefing.tasks.sync_market_data_task.retry",
            side_effect=RuntimeError("retry-called"),
        ) as mock_retry:
            with self.assertRaisesRegex(RuntimeError, "retry-called"):
                sync_market_data_task.run()

        mock_retry.assert_called_once()

    @patch(
        "apps.briefing.tasks.refresh_market_prices",
        return_value={
            "status": "partial",
            "failed": [{"reason": "PARSER_ERROR"}],
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
        },
    )
    def test_sync_market_data_task_keeps_partial_when_not_retryable(self, _mock_refresh):
        with patch("apps.briefing.tasks.sync_market_data_task.retry") as mock_retry:
            result = sync_market_data_task.run()

        self.assertEqual(result["status"], "partial")
        mock_retry.assert_not_called()

    @patch(
        "apps.briefing.tasks.collect_interest_snapshot",
        return_value={"status": "error", "message": "interest failed"},
    )
    def test_sync_interest_data_task_retries_on_error(self, _mock_collect):
        with patch(
            "apps.briefing.tasks.sync_interest_data_task.retry",
            side_effect=RuntimeError("retry-interest"),
        ) as mock_retry:
            with self.assertRaisesRegex(RuntimeError, "retry-interest"):
                sync_interest_data_task.run()

        mock_retry.assert_called_once()

    @patch(
        "apps.briefing.tasks.collect_news_items",
        return_value={"status": "error", "message": "news failed"},
    )
    def test_sync_news_data_task_retries_on_error(self, _mock_collect):
        with patch(
            "apps.briefing.tasks.sync_news_data_task.retry",
            side_effect=RuntimeError("retry-news"),
        ) as mock_retry:
            with self.assertRaisesRegex(RuntimeError, "retry-news"):
                sync_news_data_task.run()

        mock_retry.assert_called_once()

    @patch(
        "apps.briefing.tasks.create_daily_briefing",
        return_value=SimpleNamespace(
            generated_by="gemini-fallback",
            briefing_date=date(2026, 2, 13),
        ),
    )
    def test_generate_daily_briefing_task_retries_on_fallback(self, _mock_generate):
        with patch(
            "apps.briefing.tasks.generate_daily_briefing_task.retry",
            side_effect=RuntimeError("retry-briefing"),
        ) as mock_retry:
            with self.assertRaisesRegex(RuntimeError, "retry-briefing"):
                generate_daily_briefing_task.run()

        mock_retry.assert_called_once()

    @patch(
        "apps.briefing.tasks.send_daily_briefing_email",
        return_value={"status": "success", "email_status": DailyBriefing.EmailStatus.SENT},
    )
    def test_send_daily_briefing_email_task_uses_previous_briefing_date(self, mock_send):
        result = send_daily_briefing_email_task.run(previous_result={"briefing_date": "2026-02-12"})

        self.assertEqual(result["status"], "success")
        mock_send.assert_called_once_with(briefing_date=date(2026, 2, 12))

    @patch(
        "apps.briefing.tasks.send_daily_briefing_email",
        return_value={"status": "error", "message": "email failed"},
    )
    def test_send_daily_briefing_email_task_retries_on_error(self, _mock_send):
        with patch(
            "apps.briefing.tasks.send_daily_briefing_email_task.retry",
            side_effect=RuntimeError("retry-email"),
        ) as mock_retry:
            with self.assertRaisesRegex(RuntimeError, "retry-email"):
                send_daily_briefing_email_task.run()

        mock_retry.assert_called_once()

    @patch(
        "apps.briefing.tasks.send_daily_briefing_email",
        return_value={
            "status": "partial",
            "email_status": DailyBriefing.EmailStatus.FAILED,
        },
    )
    def test_send_daily_briefing_email_task_retries_on_failed_email_status(self, _mock_send):
        with patch(
            "apps.briefing.tasks.send_daily_briefing_email_task.retry",
            side_effect=RuntimeError("retry-email-failed"),
        ) as mock_retry:
            with self.assertRaisesRegex(RuntimeError, "retry-email-failed"):
                send_daily_briefing_email_task.run()

        mock_retry.assert_called_once()

    def test_run_daily_pipeline_task_returns_async_task_id(self):
        mock_async_result = SimpleNamespace(id="pipeline-task-id")
        mock_workflow = MagicMock()
        mock_workflow.apply_async.return_value = mock_async_result

        with patch("apps.briefing.tasks.chain", return_value=mock_workflow) as mock_chain:
            result = run_daily_pipeline_task()

        self.assertEqual(result, {"status": "success", "task_id": "pipeline-task-id"})
        mock_chain.assert_called_once()
        self.assertEqual(len(mock_chain.call_args.args), 5)
