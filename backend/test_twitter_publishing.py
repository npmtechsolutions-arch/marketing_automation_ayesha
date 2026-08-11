import sys
import unittest
from unittest.mock import MagicMock, patch

from app.services.platform_service import PlatformService


class TestTwitterPublishing(unittest.TestCase):

    def test_mock_token_returns_simulated_success(self):
        """Explicit mock tokens return simulated success."""
        mock_platform = MagicMock()
        mock_platform.access_token = "mock_token_123"
        mock_platform.config = {"username": "testuser"}

        mock_post = MagicMock()
        mock_post.content = "Test tweet content"
        mock_post.media_urls = None

        result = PlatformService.publish_to_twitter(mock_post, mock_platform)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["platform"], "twitter")
        self.assertIn("https://x.com/testuser/status/", result["post_url"])
        print("PASS: test_mock_token_returns_simulated_success passed")

    @patch("httpx.Client")
    def test_real_token_successful_publishing(self, mock_httpx):
        """Real tokens post to Twitter API v2 and return live tweet URL."""
        mock_client_instance = MagicMock()
        mock_httpx.return_value.__enter__.return_value = mock_client_instance

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"data": {"id": "1829304958671"}}
        mock_client_instance.post.return_value = mock_response

        mock_platform = MagicMock()
        mock_platform.access_token = "real_oauth2_token_xyz"
        mock_platform.account_name = "SIVA"
        mock_platform.config = {"username": "sivasiv30963229"}

        mock_post = MagicMock()
        mock_post.content = "Virat Kohli — a name that transcends cricket."
        mock_post.media_urls = None

        result = PlatformService.publish_to_twitter(mock_post, mock_platform)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["external_post_id"], "1829304958671")
        self.assertEqual(result["post_url"], "https://x.com/sivasiv30963229/status/1829304958671")
        print("PASS: test_real_token_successful_publishing passed")

    @patch("httpx.Client")
    def test_real_token_error_raises_valueerror(self, mock_httpx):
        """Twitter API errors (e.g. 402 credits depleted / 401 unauthorized) raise ValueError."""
        mock_client_instance = MagicMock()
        mock_httpx.return_value.__enter__.return_value = mock_client_instance

        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.text = '{"detail":"credits depleted","status":402,"title":"Payment Required"}'
        mock_response.json.return_value = {
            "detail": "credits depleted",
            "status": 402,
            "title": "Payment Required"
        }
        mock_client_instance.post.return_value = mock_response

        mock_platform = MagicMock()
        mock_platform.access_token = "real_oauth2_token_xyz"
        mock_platform.account_name = "SIVA"
        mock_platform.config = {"username": "sivasiv30963229"}

        mock_post = MagicMock()
        mock_post.content = "Test tweet"
        mock_post.media_urls = None

        with self.assertRaises(ValueError) as ctx:
            PlatformService.publish_to_twitter(mock_post, mock_platform)

        self.assertIn("credits have been depleted", str(ctx.exception))
        print("PASS: test_real_token_error_raises_valueerror passed")


if __name__ == "__main__":
    unittest.main()
