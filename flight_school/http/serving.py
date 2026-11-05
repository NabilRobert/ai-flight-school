"""Serving an ASGI app on a free local port in a background thread, for
the MCP tool server during a run and the reference agent in tests.

Inspect runs its own event loop, so the servers get a thread and a loop
of their own. They listen on 127.0.0.1 only (X3): nothing outside the
machine can reach them.
"""

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import uvicorn
from starlette.types import ASGIApp

LOCALHOST = "127.0.0.1"
# Uvicorn starts in milliseconds; a server that isn't up after this is
# broken, and waiting longer would only hide it.
STARTUP_TIMEOUT_SECONDS = 10.0


@contextmanager
def serve_in_thread(app: ASGIApp, port: int = 0) -> Iterator[str]:
    """Serve `app` while the block runs; yields its base URL. Port 0
    picks a free port."""
    server = uvicorn.Server(uvicorn.Config(app, host=LOCALHOST, port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError(f"the local server on {LOCALHOST}:{port} didn't start")
        time.sleep(0.01)
    bound_port = server.servers[0].sockets[0].getsockname()[1]
    try:
        yield f"http://{LOCALHOST}:{bound_port}"
    finally:
        server.should_exit = True
        thread.join()
