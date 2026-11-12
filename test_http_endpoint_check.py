import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from http_endpoint_check import NoRedirect, check_endpoint, read_config


SCRIPT = Path(__file__).with_name("http_endpoint_check.py")


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/slow":
            time.sleep(0.2)
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/")
        else:
            self.send_response(200 if self.path in ("/", "/slow") else 404)
        self.end_headers()

    do_HEAD = do_GET

    def log_message(self, *_args):
        pass


class HttpEndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.addClassCleanup(server.server_close)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(server.shutdown)
        cls.base = f"http://127.0.0.1:{server.server_port}"
        cls.opener = build_opener(ProxyHandler({}), NoRedirect())

    def endpoint(self, path, *codes, **options):
        return {"name": "fixture", "url": self.base + path, "expect": list(codes), **options}

    def write_config(self, endpoint):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        config = Path(temporary.name) / "endpoints.json"
        config.write_text(json.dumps({"endpoints": [endpoint]}), encoding="utf-8")
        return config

    def test_expected_error_code_and_redirect(self):
        missing = check_endpoint(self.endpoint("/missing", 404), 1, self.opener)
        redirect = check_endpoint(self.endpoint("/redirect", 302), 1, self.opener)
        self.assertEqual((missing["status"], missing["ok"]), (404, True))
        self.assertEqual((redirect["status"], redirect["ok"]), (302, True))

    def test_timeout_returns_diagnostic(self):
        result = check_endpoint(self.endpoint("/slow", 200), 0.03, self.opener)
        self.assertIsNone(result["status"])
        self.assertEqual(result["error"], "zaman aşımı")

    def test_latency_limit(self):
        result = check_endpoint(self.endpoint("/slow", 200, max_latency_ms=25), 1, self.opener)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["error"], "yanıt süresi sınırı aşıldı")

    def test_invalid_url_and_mistyped_fields(self):
        for endpoint in (
            {"name": "invalid", "url": "file:///some-path", "expect": [200]},
            self.endpoint("/", 200, max_latecy_ms=10),
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                read_config(self.write_config(endpoint))

    def test_cli_json_with_mismatched_status(self):
        config = self.write_config(self.endpoint("/", 204, method="HEAD"))
        command = [sys.executable, str(SCRIPT), str(config), "--json"]
        env = {**os.environ, "NO_PROXY": "127.0.0.1"}
        result = subprocess.run(command, capture_output=True, env=env, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        report, = json.loads(result.stdout)
        self.assertEqual(report["status"], 200)
        self.assertFalse(report["ok"])
        self.assertNotIn("url", report)


if __name__ == "__main__":
    unittest.main()
