import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app.main import app


class ExtensionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.payload = {
            "marketplace": "mercadolivre",
            "url": "https://produto.mercadolivre.com.br/MLB-123",
            "canonical_url": "https://produto.mercadolivre.com.br/MLB-123",
            "captured_at": "2026-09-23T12:00:00Z",
            "title": "Produto de teste",
            "price": 99.9,
            "currency": "BRL",
            "seller": "Loja teste",
            "listing_id": "MLB123",
            "brand": "Marca teste",
            "condition": "NewCondition",
            "rating": 4.8,
            "review_count": 125,
            "sold_count": 42,
            "image_count": 6,
            "shipping": "Frete grátis",
            "is_catalog": False,
            "is_sponsored": False,
            "source_map": {"title": "JSON-LD Product.name", "price": "JSON-LD Product.offers.price"},
            "confidence": "high",
            "evidence": ["title: JSON-LD Product.name", "price: JSON-LD Product.offers.price"],
            "warnings": [],
        }

    def test_snapshot_is_persisted_and_listed(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "snapshots.json"
            with patch("services.api.app.extension_api.SNAPSHOTS_FILE", target):
                created = self.client.post("/v1/extension/snapshots", json=self.payload)
                listed = self.client.get("/v1/extension/snapshots")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["verified"])
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["title"], "Produto de teste")
        self.assertEqual(listed.json()[0]["listing_id"], "MLB123")
        self.assertEqual(listed.json()[0]["review_count"], 125)
        self.assertEqual(listed.json()[0]["source_map"]["price"], "JSON-LD Product.offers.price")

    def test_unknown_marketplace_is_rejected(self):
        payload = {**self.payload, "marketplace": "desconhecido"}
        response = self.client.post("/v1/extension/snapshots", json=payload)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
