# SPDX-License-Identifier: Apache-2.0
"""Research-only read API over the existing support ledger; no writes or hydration.

A trusted in-process caller supplies identity, object policy, clock and an anchor.
No request header, query or browser value can supply those authorities. Hashes
are continuity evidence relative to a retained head, not signatures or truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
from pathlib import Path
import re
import sqlite3
from typing import Callable
from urllib.parse import parse_qs

import support_memory as sm
from impact_delta import delta_states

CORE_SHA256 = "7dfdc9419b210a146a06b0839deff299117496f07eff882d292c1c0eb7ad6040"
STATES = {"SUPPORTED", "UNSUPPORTED", "WITHDRAWN", "EXPIRED", "RIGHTS_UNAVAILABLE"}
MAX_NODES = 128
MAX_BYTES = 262144
MAX_CUT_CHECKS = 256


@dataclass(frozen=True)
class Context:
    principal: str
    tenant: str


@dataclass(frozen=True)
class Anchor:
    head: str
    observed_at: int
    policy_revision: str


class BoundaryError(Exception):
    def __init__(self, code: str, status: int = 503):
        super().__init__(code)
        self.code, self.status = code, status


class ReadOnlyMemory(sm.SupportMemory):
    def __init__(self, path: Path):
        path = path.resolve(strict=True)
        self.db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                  isolation_level=None, timeout=0.1)
        self.db.execute("PRAGMA query_only=ON")


def states_for(nodes: dict, withdrawn: set, now: int) -> dict:
    """Pure finite replay of v0.2 support semantics; not source-truth validation."""
    result = {}
    for key, node in nodes.items():
        if key in withdrawn:
            state = "WITHDRAWN"
        elif node["read_allowed"] is not True:
            state = "RIGHTS_UNAVAILABLE"
        elif now >= node["expires_at"]:
            state = "EXPIRED"
        elif node["op"] == "source":
            state = "SUPPORTED"
        else:
            state = "SUPPORTED" if any(all(result[p] == "SUPPORTED" for p in term)
                                        for term in node["supports"]) else "UNSUPPORTED"
        result[key] = state
    return result


def ancestors(nodes: dict, target: str) -> set:
    found, todo = set(), [target]
    while todo:
        key = todo.pop()
        if key in found:
            continue
        found.add(key)
        if nodes[key]["op"] == "claim":
            todo.extend(p for term in nodes[key]["supports"] for p in term)
    return found


def minimum_cuts(nodes: dict, withdrawn: set, now: int, target: str,
                 *, max_width: int = 3, max_checks: int = MAX_CUT_CHECKS) -> dict:
    """Inclusion-minimal source-removal sets within an explicit finite search budget."""
    if type(max_width) is not int or not 1 <= max_width <= 8:
        raise ValueError("CUT_WIDTH")
    if type(max_checks) is not int or not 1 <= max_checks <= MAX_CUT_CHECKS:
        raise ValueError("CUT_BUDGET")
    states = states_for(nodes, withdrawn, now)
    if states[target] != "SUPPORTED":
        return {"state": "ALREADY_UNSUPPORTED", "sets": [], "checks": 0,
                "search_complete": True, "max_width": max_width}
    sources = sorted(k for k in ancestors(nodes, target)
                     if nodes[k]["op"] == "source" and states[k] == "SUPPORTED")
    cuts, checks, considered, exhausted = [], 0, 0, False
    for width in range(1, min(max_width, len(sources)) + 1):
        for items in combinations(sources, width):
            if considered >= max_checks:
                exhausted = True
                break
            considered += 1
            removal = set(items)
            if any(set(cut) <= removal for cut in cuts):
                continue
            checks += 1
            if states_for(nodes, withdrawn | removal, now)[target] != "SUPPORTED":
                cuts.append(list(items))
        if exhausted:
            break
    complete = not exhausted and len(sources) <= max_width
    return {"state": "FINITE_SEARCH" if complete else "BOUNDED_PARTIAL",
            "sets": cuts, "checks": checks, "candidates_considered": considered,
            "candidate_budget": max_checks, "candidate_sources": len(sources),
            "search_complete": complete, "max_width": max_width,
            "interpretation": "Minimal only within inspected version-bound support graph; not causal evidence."}


class AssuranceService:
    """Trusted control inputs stay server-side. Every read revalidates the anchor."""
    def __init__(self, ledger: Path, anchor: Callable[[], Anchor],
                 policy: Callable[[Context, str | None, str], bool],
                 clock: Callable[[], int], *, ttl_seconds: int = 60,
                 data_class: str = "CONTROLLER_SUPPLIED_HANDLES"):
        if sha256(Path(sm.__file__).read_bytes()).hexdigest() != CORE_SHA256:
            raise BoundaryError("SUPPORT_CORE_VERSION_DRIFT")
        if type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 300:
            raise ValueError("TTL_BOUND")
        if data_class not in {"SYNTHETIC_DEMO", "CONTROLLER_SUPPLIED_HANDLES"}:
            raise ValueError("DATA_CLASS")
        self.ledger, self.anchor, self.policy, self.clock = ledger, anchor, policy, clock
        self.ttl, self.data_class = ttl_seconds, data_class

    def _anchor(self, now: int) -> Anchor:
        sm.integer(now)
        anchor = self.anchor()
        if type(anchor) is not Anchor or re.fullmatch(r"[0-9a-f]{64}", anchor.head) is None:
            raise BoundaryError("TRUSTED_ANCHOR_UNAVAILABLE")
        sm.integer(anchor.observed_at)
        sm.pin(anchor.policy_revision)
        if now < anchor.observed_at:
            raise BoundaryError("CLOCK_UNCERTAIN")
        if now >= anchor.observed_at + self.ttl:
            raise BoundaryError("STALE_ANCHOR")
        return anchor

    def snapshot(self, ctx: Context, *, expected_head: str | None = None,
                 withdraw: tuple[str, ...] = (), target: str | None = None) -> dict:
        if type(ctx) is not Context:
            raise BoundaryError("IDENTITY_REQUIRED", 401)
        sm.identifier(ctx.principal)
        sm.identifier(ctx.tenant)
        if self.policy(ctx, None, "read") is not True:
            raise BoundaryError("READ_DENIED", 403)
        now = self.clock()
        anchor = self._anchor(now)
        if expected_head is not None and expected_head != anchor.head:
            raise BoundaryError("STALE_VIEW_HEAD", 409)
        if (withdraw or target) and expected_head is None:
            raise BoundaryError("EXPECTED_HEAD_REQUIRED", 428)
        if type(withdraw) is not tuple or len(withdraw) > 8 or len(set(withdraw)) != len(withdraw):
            raise BoundaryError("INVALID_WITHDRAWAL_SET", 422)
        if any(type(k) is not str for k in withdraw):
            raise BoundaryError("INVALID_WITHDRAWAL_SET", 422)
        memory = ReadOnlyMemory(self.ledger)
        try:
            memory.db.execute("BEGIN")
            count, payload_bytes = memory.db.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(CAST(payload AS BLOB))),0) FROM events").fetchone()
            if count > sm.MAX_EVENTS or payload_bytes > 4 * 1024 * 1024:
                raise BoundaryError("LEDGER_READ_BUDGET")
            events, head = memory._events()
            if head != anchor.head:
                raise BoundaryError("LEDGER_ANCHOR_MISMATCH", 409)
            nodes, removed = sm._reduce(events)
            if len(nodes) > MAX_NODES:
                raise BoundaryError("GRAPH_BUDGET")
            own = {k: n for k, n in nodes.items() if n["tenant"] == ctx.tenant}
            visible = {k for k, n in own.items()
                       if n["read_allowed"] is True and self.policy(ctx, k, "view") is True}
            if any(k not in visible or own[k]["op"] != "source" for k in withdraw):
                raise BoundaryError("OBJECT_NOT_AVAILABLE", 404)
            if target is not None and (target not in visible or own[target]["op"] != "claim"):
                raise BoundaryError("OBJECT_NOT_AVAILABLE", 404)
            final_now = self.clock()
            if final_now < now:
                raise BoundaryError("CLOCK_UNCERTAIN")
            if self._anchor(final_now) != anchor:
                raise BoundaryError("ANCHOR_CHANGED_DURING_READ", 409)
            if self.policy(ctx, None, "read") is not True:
                raise BoundaryError("READ_DENIED", 403)
            before = states_for(own, removed, final_now)
            after = delta_states(own, removed, final_now, set(withdraw), before)
            objects = []
            for key, node in own.items():
                if key not in visible:
                    continue
                redacted = not ancestors(own, key) <= visible
                row = {"id": key, "kind": node["op"], "revision": node["revision"],
                       "content_sha256": node["content_sha256"], "expires_at": node["expires_at"],
                       "state": "UNAVAILABLE" if redacted else before[key],
                       "scenario_state": "UNAVAILABLE" if redacted else after[key],
                       "explanation_redacted": redacted,
                       "supports": [] if redacted else node.get("supports", [])}
                objects.append(row)
            cuts = None
            if target is not None:
                if not ancestors(own, target) <= visible:
                    raise BoundaryError("SUPPORT_NOT_DISCLOSABLE", 403)
                cuts = minimum_cuts(own, removed, final_now, target)
            remaining_expiries = [n["expires_at"] for k, n in own.items()
                                  if k in visible and n["expires_at"] > final_now]
            valid_until = min([anchor.observed_at + self.ttl, final_now + 30] + remaining_expiries)
            result = {"schema": "szl.assurance-surface/v0.3", "state": "OBSERVED",
                      "data_class": self.data_class, "tenant": ctx.tenant,
                      "head": head, "policy_revision": anchor.policy_revision,
                      "observed_at": anchor.observed_at, "evaluated_at": final_now,
                      "valid_until": valid_until, "objects": objects,
                      "scenario": {"hypothetical": True, "withdraw": list(withdraw),
                                   "persistent_mutations": 0, "target": target, "cut_sets": cuts},
                      "capabilities": {"content_hydration": False, "execution": False,
                                       "training": False, "promotion": False},
                      "qualifications": {"truth_verified": False, "production_qualified": False,
                                         "independent_witness": False},
                      "visible_object_count": len(objects)}
            # Trusted callbacks must version policy changes. Recheck each disclosed
            # object and anchor immediately before return; this is not an external
            # action lease or a distributed atomic authorization transaction.
            finish = self.clock()
            sm.integer(finish)
            if finish < final_now:
                raise BoundaryError("CLOCK_UNCERTAIN")
            if finish >= valid_until:
                raise BoundaryError("VIEW_EXPIRED_DURING_READ")
            if self._anchor(finish) != anchor:
                raise BoundaryError("ANCHOR_CHANGED_DURING_READ", 409)
            if self.policy(ctx, None, "read") is not True or any(
                    self.policy(ctx, key, "view") is not True for key in visible):
                raise BoundaryError("READ_DENIED", 403)
            result["snapshot_sha256"] = sm.digest(result)
            if len(sm.canonical(result)) > MAX_BYTES:
                raise BoundaryError("RESPONSE_BYTE_BUDGET")
            return result
        finally:
            if memory.db.in_transaction:
                memory.db.execute("ROLLBACK")
            memory.close()


class AssuranceApp:
    """Mountable WSGI boundary. Trusted middleware must inject Context, not headers."""
    def __init__(self, service: AssuranceService):
        self.service = service
        self.assets = Path(__file__).with_name("assurance_web")

    def __call__(self, environ, start_response):
        headers = [("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                   ("Referrer-Policy", "no-referrer"), ("X-Frame-Options", "DENY"),
                   ("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")]
        status, content_type = 200, "application/json; charset=utf-8"
        try:
            if environ.get("REQUEST_METHOD") != "GET":
                raise BoundaryError("METHOD_NOT_ALLOWED", 405)
            ctx = environ.get("szl.assurance.context")
            if type(ctx) is not Context:
                raise BoundaryError("IDENTITY_REQUIRED", 401)
            if self.service.policy(ctx, None, "read") is not True:
                raise BoundaryError("READ_DENIED", 403)
            route = environ.get("PATH_INFO", "")
            assets = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/assurance.mjs": ("assurance.mjs", "text/javascript; charset=utf-8"),
                      "/assurance.css": ("assurance.css", "text/css; charset=utf-8")}
            raw_query = environ.get("QUERY_STRING", "")
            if len(raw_query) > 2048:
                raise BoundaryError("QUERY_BUDGET", 422)
            if route in assets:
                if raw_query:
                    raise BoundaryError("QUERY_NOT_ALLOWED", 422)
                name, content_type = assets[route]
                body = (self.assets / name).read_bytes()
            elif route in {"/api/snapshot", "/api/scenario", "/api/cuts"}:
                query = parse_qs(raw_query, keep_blank_values=True, strict_parsing=True,
                                 max_num_fields=9)
                allowed = {"/api/snapshot": set(), "/api/scenario": {"withdraw"}, "/api/cuts": {"target"}}[route]
                if not set(query) <= allowed:
                    raise BoundaryError("QUERY_NOT_ALLOWED", 422)
                target = None
                if route == "/api/cuts":
                    if set(query) != {"target"} or len(query["target"]) != 1 or not query["target"][0]:
                        raise BoundaryError("TARGET_REQUIRED", 422)
                    target = query["target"][0]
                expected = environ.get("HTTP_IF_MATCH")
                if route != "/api/snapshot" and expected is None:
                    raise BoundaryError("EXPECTED_HEAD_REQUIRED", 428)
                body = sm.canonical(self.service.snapshot(ctx, expected_head=expected,
                                  withdraw=tuple(query.get("withdraw", [])), target=target))
            else:
                raise BoundaryError("NOT_FOUND", 404)
        except BoundaryError as exc:
            content_type = "application/json; charset=utf-8"
            status = exc.status
            body = sm.canonical({"schema": "szl.assurance-error/v0.3", "state": "UNAVAILABLE",
                                 "reason": exc.code, "capabilities": {"execution": False}})
        except Exception:
            content_type = "application/json; charset=utf-8"
            status = 503
            body = sm.canonical({"schema": "szl.assurance-error/v0.3", "state": "UNAVAILABLE",
                                 "reason": "EVIDENCE_OR_CONTRACT_UNAVAILABLE",
                                 "capabilities": {"execution": False}})
        labels = {200: "OK", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
                  405: "Method Not Allowed", 409: "Conflict", 422: "Unprocessable Content",
                  428: "Precondition Required", 503: "Service Unavailable"}
        start_response(f"{status} {labels[status]}", headers + [("Content-Type", content_type),
                                                            ("Content-Length", str(len(body)))])
        return [body]
