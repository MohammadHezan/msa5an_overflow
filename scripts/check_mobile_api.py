"""Run the real TypeScript phone client against a disposable Flask server.

No preview, join code, environment file, or persistent database is needed.
The harness adds two test-only routes that never exist in the real app:
- POST /__harness__/batches/<id>/delete expires a batch the way cleanup does;
- POST /__harness__/sessions/verify?firstName=<name> (with the session's bearer token) marks that
  session as a verified student, for tests that only need a verified booking.
It also makes this disposable server issue the verification code 123456 (the next code,
after a resend, is 123457), because real codes are only written to the server log.
"""

from pathlib import Path
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from types import SimpleNamespace

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from store import database, find_token, now  # noqa: E402
import student_verification  # noqa: E402
from urllib.parse import parse_qs  # noqa: E402

HARNESS_CODE = 123456

HARNESS_PREFIX = "/__harness__/batches/"
VERIFY_PATH = "/__harness__/sessions/verify"


def verify_session(environ):
    """Give the bearer token a verified student profile; returns False for an unknown token."""
    token = environ.get("HTTP_AUTHORIZATION", "").partition(" ")[2].strip()
    first_name = parse_qs(environ.get("QUERY_STRING", "")).get("firstName", ["Student"])[0]
    with app.app_context():
        db = database()
        with db:
            row = find_token(db, token) if token else None
            if not row or row["role"] != "student":
                return False
            school = db.execute("SELECT id FROM universities WHERE email_domain = 'bau.edu.jo'").fetchone()["id"]
            student_id = db.execute(
                "INSERT INTO students (university, email, first_name, verified_at) VALUES (?, ?, ?, ?)",
                (school, f"{first_name.lower()}.{secrets.token_hex(4)}@bau.edu.jo", first_name, now().isoformat()),
            ).lastrowid
            db.execute("UPDATE api_tokens SET student_id = ? WHERE token_hash = ?", (student_id, row["token_hash"]))
    return True


def with_harness_routes(wsgi_app):
    """Wrap the app with test hooks that only this disposable server exposes."""
    def harness(environ, start_response):
        path = environ.get("PATH_INFO", "")
        if environ.get("REQUEST_METHOD") == "POST" and path == VERIFY_PATH:
            start_response("204 No Content" if verify_session(environ) else "401 Unauthorized", [])
            return [b""]
        if environ.get("REQUEST_METHOD") == "POST" and path.startswith(HARNESS_PREFIX) and path.endswith("/delete"):
            batch_id = path[len(HARNESS_PREFIX):-len("/delete")]
            with app.app_context():
                db = database()
                with db:
                    deleted = db.execute("DELETE FROM batches WHERE id = ?", (batch_id,)).rowcount
            start_response("204 No Content" if deleted else "404 Not Found", [])
            return [b""]
        return wsgi_app(environ, start_response)
    return harness


def main():
    with TemporaryDirectory(prefix="campus-mobile-api-") as directory:
        app.config.update(TESTING=True, DATABASE=Path(directory) / "test.sqlite")
        # Deterministic codes in this process only; everything else still uses real randomness.
        student_verification.secrets = SimpleNamespace(
            randbelow=lambda limit: HARNESS_CODE % limit, token_hex=secrets.token_hex,
        )
        # Keep an unused port reserved but not listening: a real, deterministic
        # connection refusal for the client's offline path, without mocking fetch.
        with socket.socket() as offline:
            offline.bind(("127.0.0.1", 0))
            server = make_server("127.0.0.1", 0, with_harness_routes(app), threaded=True)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                result = subprocess.run(
                    [
                        "pnpm", "exec", "tsx",
                        "tests/integration/api-flow.test.ts",
                        f"http://127.0.0.1:{server.server_port}",
                        f"http://127.0.0.1:{offline.getsockname()[1]}",
                    ],
                    cwd=ROOT / "artifacts" / "campus-connect",
                    timeout=90,
                    check=False,
                )
                return result.returncode
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
