import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app.main import app


class AgentReachRouterTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_status_exposes_read_only_channels(self):
        response = self.client.get("/v1/reach/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["installed"])
        self.assertEqual(payload["mode"], "read_only")
        self.assertGreaterEqual(payload["channel_count"], 16)
        self.assertFalse(payload["credentials_loaded"])

    def test_read_public_page_is_bounded(self):
        with patch(
            "services.api.app.reach_router.WebChannel.read",
            return_value="# Produto\nConteúdo público verificado.",
        ):
            response = self.client.post(
                "/v1/reach/read",
                json={
                    "url": "https://example.com/product",
                    "purpose": "Pesquisar informações públicas do produto",
                },
            )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["execution_mode"], "read_only")
        self.assertEqual(payload["source"], "agent-reach:jina-reader")
        self.assertIn("Produto", payload["content"])


if __name__ == "__main__":
    unittest.main()

