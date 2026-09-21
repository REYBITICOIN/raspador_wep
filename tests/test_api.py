import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app.main import app, jobs


async def fake_crawl(url):
    return {
        "title": "Produto de Teste",
        "final_url": url,
        "http_status": 200,
        "html": "<html><head><title>Produto de Teste</title></head><body>ok</body></html>",
        "text": "Produto de Teste ok",
    }


class ApiFlowTest(unittest.TestCase):
    def setUp(self):
        jobs.clear()
        self.client = TestClient(app)

    def test_health_and_complete_collection(self):
        with patch("services.api.app.main.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), patch("services.api.app.main.crawl_dynamic_page", fake_crawl):
            response = self.client.post("/v1/jobs", json={"url": "https://example.com", "instruction": "Extraia o titulo", "provider": "auto"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "completed")
        self.assertEqual(response.json()["result"]["title"], "Produto de Teste")
        self.assertEqual(self.client.get("/v1/stats").json()["completed"], 1)
        self.assertEqual(len(self.client.get("/v1/jobs").json()), 1)

    def test_private_address_is_blocked(self):
        with patch("services.api.app.main.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            response = self.client.post("/v1/jobs", json={"url": "http://localhost", "instruction": "teste", "provider": "auto"})
        self.assertEqual(response.status_code, 400)

    def test_grok_is_blocked_without_paid_authorization(self):
        response = self.client.post("/v1/jobs", json={"url": "https://example.com", "instruction": "teste", "provider": "grok"})
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
