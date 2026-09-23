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
        self.search_payload = {
            "marketplace": "mercadolivre",
            "page_type": "search",
            "url": "https://lista.mercadolivre.com.br/calca-legging-flare",
            "captured_at": "2026-09-23T12:00:00Z",
            "query": "calca legging flare",
            "visible_results": 1,
            "captured_results": 1,
            "sponsored_count": 1,
            "official_store_count": 1,
            "free_shipping_count": 1,
            "min_price": 35.9,
            "max_price": 35.9,
            "products": [{
                "position": 1, "listing_id": "MLB4182420507",
                "title": "Calça Legging Flare", "price": 35.9,
                "url": "https://produto.mercadolivre.com.br/MLB-4182420507",
                "seller": "KOENIG", "rating": 4.7,
                "shipping": "Frete grátis", "official_store": True,
                "sponsored": True, "evidence": ["DOM .poly-card"],
            }],
            "confidence": "high",
            "warnings": ["Vendas não estimadas."],
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

    def test_search_snapshot_is_persisted_and_listed(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "search-snapshots.json"
            with patch("services.api.app.extension_api.SEARCH_SNAPSHOTS_FILE", target):
                created = self.client.post("/v1/extension/search-snapshots", json=self.search_payload)
                listed = self.client.get("/v1/extension/search-snapshots")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["verified"])
        self.assertEqual(listed.json()[0]["products"][0]["listing_id"], "MLB4182420507")
        self.assertTrue(listed.json()[0]["products"][0]["sponsored"])

    def test_search_snapshot_rejects_inconsistent_count(self):
        payload = {**self.search_payload, "captured_results": 2}
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "search-snapshots.json"
            with patch("services.api.app.extension_api.SEARCH_SNAPSHOTS_FILE", target):
                response = self.client.post("/v1/extension/search-snapshots", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["verified"])

    def test_search_history_compares_real_snapshots(self):
        older_product = {**self.search_payload["products"][0], "position": 3, "price": 40.9}
        older = {
            **self.search_payload,
            "captured_at": "2026-09-23T11:00:00Z",
            "min_price": 40.9,
            "max_price": 40.9,
            "products": [older_product],
        }
        newer = {**self.search_payload, "captured_at": "2026-09-23T12:00:00Z"}
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "search-snapshots.json"
            with patch("services.api.app.extension_api.SEARCH_SNAPSHOTS_FILE", target):
                self.client.post("/v1/extension/search-snapshots", json=older)
                self.client.post("/v1/extension/search-snapshots", json=newer)
                response = self.client.get("/v1/extension/search-history", params={"query": "  CALCA LEGGING FLARE "})
        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertEqual(history["snapshot_count"], 2)
        self.assertTrue(history["has_comparison"])
        self.assertEqual(history["competitors"][0]["position_change"], 2)
        self.assertEqual(history["competitors"][0]["price_change"], -5.0)
        self.assertEqual(history["competitors"][0]["trend"], "rising")

    def test_search_intelligence_uses_observed_title_frequency(self):
        second_product = {
            **self.search_payload["products"][0], "position": 2, "listing_id": "MLB999",
            "title": "Calça Flare Feminina Cintura Alta", "price": 64.1,
            "seller": "OUTRA LOJA", "sponsored": False, "official_store": False,
        }
        snapshot = {
            **self.search_payload, "visible_results": 2, "captured_results": 2,
            "products": [self.search_payload["products"][0], second_product],
        }
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "search-snapshots.json"
            with patch("services.api.app.extension_api.SEARCH_SNAPSHOTS_FILE", target):
                self.client.post("/v1/extension/search-snapshots", json=snapshot)
                response = self.client.get("/v1/extension/search-intelligence", params={"query": "CALCA LEGGING FLARE"})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["found"])
        terms = {item["term"]: item for item in result["keyword_frequency"]}
        self.assertEqual(terms["calca"]["count"], 2)
        self.assertEqual(terms["flare"]["coverage_percent"], 100.0)
        self.assertEqual(result["market"]["median_price"], 50.0)
        self.assertIn("não representa volume de busca", result["method"])

    def test_unknown_marketplace_is_rejected(self):
        payload = {**self.payload, "marketplace": "desconhecido"}
        response = self.client.post("/v1/extension/snapshots", json=payload)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
