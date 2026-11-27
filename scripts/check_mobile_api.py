"""Run the real TypeScript phone client against a disposable Flask server.

No preview, join code, environment file, or persistent database is needed.
The harness adds one test-only route, POST /__harness__/batches/<id>/delete, so the
client test can expire a batch the way cleanup does; it never exists in the real app.
"""

from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread

from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from store import database  # noqa: E402

HARNESS_PREFIX = "/__harness__/batches/"


def with_harness_routes(wsgi_app):
    """Wrap the app with a delete-batch hook that only this disposable server exposes."""
    def harness(environ, start_response):
        path = environ.get("PATH_INFO", "")
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
