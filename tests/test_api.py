import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from services.api.app.main import app, jobs


class FakeHttpClient:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url):
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"<html><head><title>Produto de Teste</title></head><body>ok</body></html>",
            request=httpx.Request("GET", url),
        )


class ApiFlowTest(unittest.TestCase):
    def setUp(self):
        jobs.clear()
        self.client = TestClient(app)

    def test_health_and_complete_collection(self):
        with patch("services.api.app.main.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]), patch("services.api.app.main.httpx.Client", FakeHttpClient):
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
