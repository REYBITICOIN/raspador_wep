import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app import local_memory
from services.api.app.main import app


class LocalMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.paths = patch.multiple(
            local_memory,
            DB_PATH=root / "database" / "commerce.db",
            VAULT_PATH=root / "obsidian" / "TOCA_KNOWLEDGE",
        )
        self.paths.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.paths.stop()
        self.temp.cleanup()

    def test_memory_is_saved_to_sqlite_and_obsidian(self):
        created = self.client.post(
            "/v1/memory",
            json={
                "kind": "decision",
                "title": "Usar agentes sob demanda",
                "content": "Carregar somente o especialista necessário para economizar tokens.",
                "tags": ["agentes", "arquitetura"],
            },
        )
        self.assertEqual(created.status_code, 201)
        note = Path(created.json()["note_path"])
        self.assertTrue(note.exists())
        self.assertTrue(local_memory.DB_PATH.exists())

        found = self.client.get("/v1/memory/search", params={"q": "especialista"})
        self.assertEqual(found.status_code, 200)
        self.assertEqual(len(found.json()), 1)
        self.assertEqual(found.json()[0]["title"], "Usar agentes sob demanda")


if __name__ == "__main__":
    unittest.main()

