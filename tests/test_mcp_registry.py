import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app.main import app


class MCPRegistryTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_policy_blocks_automatic_high_risk_execution(self):
        response = self.client.get("/v1/mcp/policy")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["unknown_servers_auto_start"])
        self.assertIn("process.kill", payload["blocked_without_explicit_confirmation"])

    def test_local_scan_finds_windows_mcp_without_starting_it(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "mcp_config.json"
            config.write_text(json.dumps({
                "mcpServers": {
                    "windows-sistema": {
                        "command": "py",
                        "args": ["-3.14", "-m", "windows_mcp", "serve"],
                    }
                }
            }), encoding="utf-8")
            with patch(
                "services.api.app.mcp_registry._config_candidates",
                return_value=[config],
            ):
                response = self.client.post("/v1/mcp/scan-local")
        self.assertEqual(response.status_code, 200)
        server = response.json()["servers"][0]
        self.assertEqual(server["name"], "windows-sistema")
        self.assertEqual(server["risk"], "high")
        self.assertTrue(server["requires_human_approval"])
        self.assertFalse(server["auto_start_allowed"])

    def test_status_reports_discovery_mode(self):
        with patch(
            "services.api.app.mcp_registry.scan_local_configs",
            return_value={"configs_found": 1, "servers": [], "errors": []},
        ):
            response = self.client.get("/v1/mcp/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["mode"], "discover_validate_plan")
        self.assertFalse(response.json()["automatic_connection"])


if __name__ == "__main__":
    unittest.main()
