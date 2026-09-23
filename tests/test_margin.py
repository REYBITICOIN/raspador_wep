import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from services.api.app.main import app


class MarginCalculatorTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_margin_calculation_with_known_values(self):
        response = self.client.post(
            "/v1/margins/calculate",
            json={
                "sale_price": 100,
                "acquisition_cost": 40,
                "commission_percent": 15,
                "tax_percent": 5,
                "fixed_fee": 5,
                "shipping_cost": 10,
                "packaging_cost": 2,
                "other_cost": 3,
                "desired_margin_percent": 20,
            },
        )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["variable_fees"], 20.0)
        self.assertEqual(result["fixed_costs"], 60.0)
        self.assertEqual(result["net_profit"], 20.0)
        self.assertEqual(result["net_margin_percent"], 20.0)
        self.assertEqual(result["break_even_price"], 75.0)
        self.assertEqual(result["desired_sale_price"], 100.0)
        self.assertEqual(result["net_revenue"], 80.0)
        self.assertEqual(result["contribution_margin"], 60.0)
        self.assertEqual(result["roi_percent"], 50.0)
        self.assertEqual(result["markup_percent"], 150.0)
        self.assertEqual(result["fee_breakdown"]["commission"], 15.0)
        self.assertEqual(result["fee_breakdown"]["tax"], 5.0)
        self.assertEqual(result["fee_source"], "manual_until_official_quote_is_connected")
        self.assertTrue(result["profitable"])

    def test_official_mercadolivre_quote_maps_fee_breakdown(self):
        official = Mock()
        official.is_error = False
        official.json.return_value = [{
            "listing_type_id": "gold_special",
            "sale_fee_amount": 40.2,
            "sale_fee_details": {
                "percentage_fee": 15,
                "fixed_fee": 6,
                "financing_add_on_fee": 0,
            },
        }]
        with patch("services.api.app.margin.call_with_auto_refresh", return_value=official):
            response = self.client.post(
                "/v1/margins/mercadolivre/quote",
                json={
                    "price": 228,
                    "category_id": "MLB1430",
                    "listing_type_id": "gold_special",
                },
            )
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["commission_percent"], 15.0)
        self.assertEqual(result["fixed_fee"], 6.0)
        self.assertEqual(result["sale_fee_amount"], 40.2)
        self.assertEqual(result["source"], "mercadolivre_official_api")

    def test_margin_rejects_impossible_rates(self):
        response = self.client.post(
            "/v1/margins/calculate",
            json={
                "sale_price": 100,
                "acquisition_cost": 40,
                "commission_percent": 70,
                "tax_percent": 30,
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

