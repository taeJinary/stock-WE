from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from services.briefing_generator import _generate_with_gemini


class BriefingGeneratorTests(SimpleTestCase):
    @override_settings(
        GEMINI_MODEL="gemini-2.5-flash-lite",
        GEMINI_API_KEY="header-api-key",
    )
    @patch("services.briefing_generator.httpx.Client")
    def test_generate_with_gemini_uses_header_auth(self, mock_client_cls):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "generated text"}],
                    }
                }
            ]
        }
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        result = _generate_with_gemini("prompt text")

        self.assertEqual(result, "generated text")
        mock_client_cls.assert_called_once_with(
            timeout=20.0,
            headers={"x-goog-api-key": "header-api-key"},
        )
        mock_client.post.assert_called_once()
        post_kwargs = mock_client.post.call_args.kwargs
        self.assertNotIn("params", post_kwargs)

    @override_settings(
        GEMINI_MODEL="gemini-2.5-flash-lite",
        GEMINI_API_KEY="header-api-key",
    )
    @patch("services.briefing_generator.httpx.Client")
    def test_generate_with_gemini_raises_when_text_missing(self, mock_client_cls):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"candidates": []}
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client

        with self.assertRaises(ValueError):
            _generate_with_gemini("prompt text")
