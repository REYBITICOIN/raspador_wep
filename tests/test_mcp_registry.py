import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def test_safe_probe_reports_real_handshake_shape(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "connected": True,
                "tool_count": 20,
                "tools": ["Wait"],
                "safe_test_passed": True,
                "writes_performed": False,
            }) + "\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temp:
            python = Path(temp) / "python.exe"
            probe = Path(temp) / "probe.py"
            python.touch()
            probe.touch()
            with patch("services.api.app.mcp_registry.WINDOWS_MCP_PYTHON", python), patch(
                "services.api.app.mcp_registry.WINDOWS_MCP_PROBE", probe
            ), patch("services.api.app.mcp_registry.subprocess.run", return_value=completed):
                response = self.client.post("/v1/mcp/probe/windows-sistema")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["connected"])
        self.assertTrue(payload["safe_test_passed"])
        self.assertFalse(payload["writes_performed"])
        self.assertEqual(payload["execution_policy"], "safe_probe_only")

    def test_approved_read_only_action_executes_once(self):
        with tempfile.TemporaryDirectory() as temp:
            approvals = Path(temp) / "approvals.json"
            with patch("services.api.app.mcp_registry.APPROVALS_FILE", approvals):
                created = self.client.post("/v1/mcp/approvals", json={
                    "tool": "Wait",
                    "purpose": "Testar espera segura",
                    "arguments": {"duration": 1},
                })
                self.assertEqual(created.status_code, 201)
                item = created.json()
                self.assertEqual(item["risk"], "read_only")
                self.assertFalse(item["executed"])
                decision = self.client.post(
                    f"/v1/mcp/approvals/{item['id']}/decision",
                    json={"decision": "approved", "note": "Aprovação de teste"},
                )
                safe_result = SimpleNamespace(
                    returncode=0,
                    stdout=json.dumps({
                        "success": True,
                        "tool": "Wait",
                        "safe_arguments": {"duration": 1},
                    }) + "\n",
                    stderr="",
                )
                with patch("services.api.app.mcp_registry.subprocess.run", return_value=safe_result):
                    executed = self.client.post(f"/v1/mcp/approvals/{item['id']}/execute")
                listed = self.client.get("/v1/mcp/approvals")
        self.assertEqual(decision.status_code, 200)
        self.assertEqual(decision.json()["state"], "approved")
        self.assertFalse(decision.json()["executed"])
        self.assertEqual(executed.status_code, 200)
        self.assertTrue(executed.json()["executed"])
        self.assertEqual(executed.json()["execution_state"], "completed")
        self.assertEqual(listed.json()["pending"], 0)

    def test_high_risk_action_stays_blocked_after_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            approvals = Path(temp) / "approvals.json"
            with patch("services.api.app.mcp_registry.APPROVALS_FILE", approvals):
                created = self.client.post("/v1/mcp/approvals", json={
                    "tool": "PowerShell",
                    "purpose": "Listar processos para diagnóstico",
                    "arguments": {"command": "Get-Process"},
                })
                item = created.json()
                self.client.post(
                    f"/v1/mcp/approvals/{item['id']}/decision",
                    json={"decision": "approved", "note": "Aprovação de teste"},
                )
                executed = self.client.post(f"/v1/mcp/approvals/{item['id']}/execute")
        self.assertEqual(item["risk"], "high")
        self.assertEqual(executed.status_code, 403)

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
