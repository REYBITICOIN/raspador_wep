import unittest

from fastapi.testclient import TestClient

from services.api.app.main import app


class AgencyRouterTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_catalog_is_lazy_and_complete(self):
        result = self.client.get("/v1/agency/status")
        self.assertEqual(result.status_code, 200)
        payload = result.json()
        self.assertTrue(payload["available"])
        self.assertGreaterEqual(payload["agent_count"], 230)
        self.assertTrue(payload["lazy_loading"])
        self.assertEqual(payload["computer_access"], "not_granted")

    def test_search_then_load_one_agent(self):
        search = self.client.get("/v1/agency/search", params={"q": "security", "limit": 3})
        self.assertEqual(search.status_code, 200)
        agents = search.json()["agents"]
        self.assertGreater(len(agents), 0)
        chosen = agents[0]
        loaded = self.client.post(
            "/v1/agency/load",
            json={"slug": chosen["slug"], "task": "Revisar somente a segurança da extensão."},
        )
        self.assertEqual(loaded.status_code, 200)
        payload = loaded.json()
        self.assertIn("TAREFA LIMITADA", payload["prompt"])
        self.assertFalse(payload["execution_authorized"])
        self.assertLess(len(payload["prompt"]), 100000)


if __name__ == "__main__":
    unittest.main()

