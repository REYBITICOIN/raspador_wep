import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.api.app import ml_oauth


class MercadoLivreOAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        ml_oauth.DATA_DIR = Path(self.temp.name)
        ml_oauth.TOKEN_FILE = ml_oauth.DATA_DIR / "token.enc"
        ml_oauth.STATE_FILE = ml_oauth.DATA_DIR / "state.json"
        self.env = patch.dict(os.environ, {
            "MERCADOLIVRE_APP_ID": "app-test",
            "MERCADOLIVRE_CLIENT_SECRET": "secret-test",
            "MERCADOLIVRE_REDIRECT_URI": "http://127.0.0.1/callback",
            "MERCADOLIVRE_TOKEN_ENCRYPTION_KEY": "encryption-test",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_token_is_encrypted_and_not_refreshed_early(self):
        saved = ml_oauth._save_token({
            "access_token": "access-one",
            "refresh_token": "refresh-one",
            "expires_in": 21600,
        })
        raw = ml_oauth.TOKEN_FILE.read_bytes()
        self.assertNotIn(b"access-one", raw)
        self.assertEqual(ml_oauth._load_token()["access_token"], "access-one")
        with patch.object(ml_oauth, "_request_token") as request:
            current = ml_oauth.refresh_access_token()
        request.assert_not_called()
        self.assertEqual(current["access_token"], saved["access_token"])

    def test_force_refresh_rotates_refresh_token(self):
        ml_oauth._save_token({
            "access_token": "access-old",
            "refresh_token": "refresh-old",
            "expires_in": 21600,
        })
        with patch.object(ml_oauth, "_request_token", return_value={
            "access_token": "access-new",
            "refresh_token": "refresh-new",
            "expires_in": 21600,
        }) as request:
            renewed = ml_oauth.refresh_access_token(force=True)
        self.assertEqual(renewed["access_token"], "access-new")
        self.assertEqual(renewed["refresh_token"], "refresh-new")
        sent = request.call_args.args[0]
        self.assertEqual(sent["refresh_token"], "refresh-old")
        self.assertEqual(ml_oauth._load_token()["refresh_token"], "refresh-new")

    def test_authorization_state_is_random_and_time_limited(self):
        first = ml_oauth.begin_authorization()
        first_state = ml_oauth.STATE_FILE.read_text(encoding="utf-8")
        second = ml_oauth.begin_authorization()
        second_state = ml_oauth.STATE_FILE.read_text(encoding="utf-8")
        self.assertIn("state=", first)
        self.assertIn("state=", second)
        self.assertNotEqual(first_state, second_state)


if __name__ == "__main__":
    unittest.main()
