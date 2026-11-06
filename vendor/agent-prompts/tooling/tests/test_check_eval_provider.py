"""Tests for the eval-provider prober (offline, canned HTTP answers)."""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / "tooling" / "check_eval_provider.py"

ANSWERS = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length or b"{}").decode("utf-8") or "{}")
        model = body.get("model", "")
        status, payload = ANSWERS.get(model, (404, {"error": "unknown model"}))
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _serve():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _run(server, *extra, key="test-key"):
    env = dict(os.environ)
    env["PROBE_TEST_KEY"] = key
    base = "http://127.0.0.1:%d/v1" % server.server_port
    return subprocess.run(
        [sys.executable, str(CHECK), "--base-url", base,
         "--api-key-env", "PROBE_TEST_KEY", *extra],
        cwd=str(ROOT), capture_output=True, text=True, env=env)


def _ok(content="ok"):
    return 200, {"choices": [{"message": {"content": content}}]}


def test_all_models_answer_exits_0():
    ANSWERS.clear()
    ANSWERS["m-ok"] = _ok()
    server = _serve()
    try:
        result = _run(server, "--models", "m-ok")
    finally:
        server.shutdown()
    assert result.returncode == 0, result.stdout
    assert "m-ok" in result.stdout
    assert "1 of 1 model(s) answered" in result.stdout


def test_payment_required_is_classified_not_a_result():
    ANSWERS.clear()
    ANSWERS["m-pay"] = (402, {"error": {"title": "Low Credit Warning!"}})
    server = _serve()
    try:
        result = _run(server, "--models", "m-pay")
    finally:
        server.shutdown()
    assert result.returncode == 1
    assert "no_credit" in result.stdout
    assert "0 of 1 model(s) answered" in result.stdout


def test_overloaded_and_unauthorized_and_unreachable_classes():
    ANSWERS.clear()
    ANSWERS["m-503"] = (503, {"error": {"message": "Provider returned error"}})
    ANSWERS["m-401"] = (401, {"error": "bad key"})
    ANSWERS["m-429"] = (429, {"error": "slow down"})
    server = _serve()
    try:
        result = _run(server, "--models", "m-503,m-401,m-429")
    finally:
        server.shutdown()
    assert result.returncode == 1
    assert "overloaded" in result.stdout
    assert "unauthorized" in result.stdout
    assert "rate_limited" in result.stdout


def test_missing_session_id_is_not_an_outage():
    ANSWERS.clear()
    ANSWERS["m-400"] = (400, {"error": "MissingSessionID"})
    server = _serve()
    try:
        result = _run(server, "--models", "m-400")
    finally:
        server.shutdown()
    assert result.returncode == 1
    assert "request_rejected" in result.stdout
    assert "overloaded" not in result.stdout


def test_empty_completion_is_not_a_pass():
    ANSWERS.clear()
    ANSWERS["m-empty"] = _ok(content="   ")
    server = _serve()
    try:
        result = _run(server, "--models", "m-empty")
    finally:
        server.shutdown()
    assert result.returncode == 1
    assert "empty" in result.stdout


def test_one_working_model_is_enough():
    ANSWERS.clear()
    ANSWERS["m-bad"] = (503, {"error": "busy"})
    ANSWERS["m-good"] = _ok()
    server = _serve()
    try:
        result = _run(server, "--models", "m-bad,m-good")
    finally:
        server.shutdown()
    assert result.returncode == 0, result.stdout
    assert "1 of 2 model(s) answered" in result.stdout


def test_missing_key_env_is_a_usage_error():
    result = subprocess.run(
        [sys.executable, str(CHECK), "--api-key-env", "DEFINITELY_UNSET_KEY_VAR"],
        cwd=str(ROOT), capture_output=True, text=True, env=dict(os.environ))
    assert result.returncode == 2
    assert "DEFINITELY_UNSET_KEY_VAR is empty" in result.stdout


def test_json_output_shape():
    ANSWERS.clear()
    ANSWERS["m-ok"] = _ok()
    server = _serve()
    try:
        result = _run(server, "--models", "m-ok", "--json")
    finally:
        server.shutdown()
    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["reachable"] is True
    assert payload["models"][0]["class"] == "ok"
    assert payload["models"][0]["model"] == "m-ok"


def test_defaults_are_the_mandated_route():
    sys.path.insert(0, str(ROOT / "tooling"))
    import check_eval_provider as probe

    assert probe.DEFAULT_BASE_URL == "https://opencode.ai/inference/go/v1"
    assert probe.DEFAULT_KEY_ENV == "OPENCODE_API_KEY"
    assert probe.DEFAULT_MODELS == ["deepseek-v4.1-flash"]


def test_headers_reach_the_endpoint():
    seen = {}

    class Recorder(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            seen.update({k.lower(): v for k, v in self.headers.items()})
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            raw = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = HTTPServer(("127.0.0.1", 0), Recorder)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = dict(os.environ, PROBE_TEST_KEY="k", OPENCODE_SESSION_ID="")
    try:
        result = subprocess.run(
            [sys.executable, str(CHECK), "--base-url",
             "http://127.0.0.1:%d/v1" % server.server_port,
             "--api-key-env", "PROBE_TEST_KEY", "--models", "m",
             "--session-header", "--session-id", "sess-9"],
            cwd=str(ROOT), capture_output=True, text=True, env=env)
    finally:
        server.shutdown()
    assert result.returncode == 0, result.stdout
    assert seen.get("x-opencode-session") == "sess-9"
    assert "Python-urllib" not in seen.get("user-agent", "")


def test_reasoning_only_answer_counts_as_reachable():
    ANSWERS.clear()
    ANSWERS["m-reason"] = (200, {"choices": [{"message": {"content": ""},
                                              "finish_reason": "length"}],
                                 "usage": {"completion_tokens_details":
                                           {"reasoning_tokens": 40}}})
    server = _serve()
    try:
        result = _run(server, "--models", "m-reason")
    finally:
        server.shutdown()
    assert result.returncode == 0, result.stdout
    assert "reasoning-only" in result.stdout


def test_key_is_never_printed():
    ANSWERS.clear()
    ANSWERS["m-401"] = (401, {"error": "bad key"})
    server = _serve()
    try:
        result = _run(server, "--models", "m-401", key="sk-secret-value-123")
    finally:
        server.shutdown()
    assert "sk-secret-value-123" not in result.stdout + result.stderr
