# SPDX-License-Identifier: Apache-2.0
"""Bounded loopback-only synthetic demo. Not production identity middleware."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import argparse
import json
import threading
import time
from wsgiref.simple_server import WSGIRequestHandler, make_server

from assurance_demo import source, claim
from assurance_surface import Anchor, AssuranceApp, AssuranceService, Context
from support_memory import SupportMemory, ZERO


@dataclass
class Demo:
    service: AssuranceService
    anchor_box: list
    ledger: Path
    root: Path
    httpd: object = None
    base_url: str = ""


def make_demo(root: Path, *, clock=lambda: int(time.time()), ttl=300) -> Demo:
    root.mkdir(parents=True, exist_ok=False)
    ledger = root / "synthetic-ledger.sqlite"
    now = clock()
    memory = SupportMemory(ledger)
    events = [source("A", expires_at=now+3600), source("B", expires_at=now+3600),
              claim("only_A", [["A"]]), claim("either", [["A"], ["B"]]),
              claim("both", [["A", "B"]]), claim("downstream", [["either"]])]
    for event in events:
        event["expires_at"] = now + 3600
    head = memory.apply(events, expected_head=ZERO, principal="research-controller",
                        authorize=lambda p, t, op: p == "research-controller" and t == "research")
    memory.close()
    anchor_box = [Anchor(head, now, "b"*40)]
    policy = lambda c, key, op: c == Context("research-controller", "research") and op in {"read", "view"}
    service = AssuranceService(ledger, lambda: anchor_box[0], policy, clock,
                               ttl_seconds=ttl, data_class="SYNTHETIC_DEMO")
    return Demo(service, anchor_box, ledger, root)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format, *args):
        pass


@contextmanager
def running_demo(root: Path, *, clock=lambda: int(time.time()), ttl=300):
    demo = make_demo(root, clock=clock, ttl=ttl)
    app = AssuranceApp(demo.service)
    expected_host = [None]
    def local_only(environ, start_response):
        # This injects a fixture identity only into a synthetic local server.
        # It must never be used as authentication for real data.
        if environ.get("REMOTE_ADDR") != "127.0.0.1" or environ.get("HTTP_HOST") != expected_host[0]:
            body = b'{"state":"UNAVAILABLE","reason":"DEMO_HOST_DENIED"}'
            start_response("403 Forbidden", [("Content-Type", "application/json"), ("Cache-Control", "no-store")])
            return [body]
        environ["szl.assurance.context"] = Context("research-controller", "research")
        return app(environ, start_response)
    httpd = make_server("127.0.0.1", 0, local_only, handler_class=QuietHandler)
    expected_host[0] = "127.0.0.1:" + str(httpd.server_port)
    demo.httpd, demo.base_url = httpd, "http://" + expected_host[0] + "/"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield demo
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=60, choices=range(1,121))
    args = parser.parse_args()
    with running_demo(args.out) as demo:
        intent = {"schema": "szl.synthetic-console-session/v1", "data_class": "SYNTHETIC_DEMO",
                  "started_at": datetime.now(timezone.utc).isoformat(), "local_url": demo.base_url,
                  "maximum_seconds": args.seconds, "production_mutations": 0}
        (args.out/"session.json").write_text(json.dumps(intent, indent=2), encoding="utf-8")
        print(json.dumps(intent), flush=True)
        time.sleep(args.seconds)
    intent["ended_at"] = datetime.now(timezone.utc).isoformat()
    intent["server_stopped"] = True
    raw = (json.dumps(intent, sort_keys=True, indent=2)+"\n").encode()
    (args.out/"completion.json").write_bytes(raw)
    print("COMPLETION_SHA256="+sha256(raw).hexdigest())
