"""Offline support provenance prototype. Not a truth oracle or production authorizer.

An OR-of-AND support DAG is rebuilt from append-only events. Source revocation
invalidates affected paths; alternative support survives. Callers must supply a
trusted policy callback. No raw/private text, model calls or network ingestion.
SQLite transactions serialize append + expected-head checks, not external use.
"""
from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
from typing import Callable

ZERO = "0" * 64
MAX_EVENTS = 2048


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def digest(value: object) -> str:
    return sha256(canonical(value)).hexdigest()


def identifier(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", value) is None:
        raise ValueError("IDENTIFIER")
    return value


def pin(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"(?:[a-f0-9]{40}|[a-f0-9]{64})", value) is None:
        raise ValueError("IMMUTABLE_PIN")
    return value


def integer(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 2**53:
        raise ValueError("INTEGER_DOMAIN")
    return value


def strict_load(raw: str) -> dict:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("DUPLICATE_KEY")
            out[key] = value
        return out
    def reject(_):
        raise ValueError("NONINTEGER_NUMBER")
    value = json.loads(raw, object_pairs_hook=pairs, parse_float=reject, parse_constant=reject)
    if type(value) is not dict:
        raise ValueError("EVENT_OBJECT")
    return value


def _reduce(events: list[dict]) -> tuple[dict, set]:
    nodes, withdrawn = {}, set()
    for event in events:
        tenant = identifier(event["tenant"])
        op = event["op"]
        if op == "withdraw":
            target = identifier(event["id"])
            if set(event) != {"tenant", "op", "id", "reason"} or event["reason"] not in {
                "REVOKED", "SUPERSEDED", "RIGHTS_WITHDRAWN"}:
                raise ValueError("WITHDRAW_SCHEMA")
            if target not in nodes or nodes[target]["tenant"] != tenant:
                raise ValueError("UNKNOWN_OR_CROSS_TENANT_NODE")
            if target in withdrawn:
                raise ValueError("ALREADY_WITHDRAWN")
            withdrawn.add(target)
            continue
        if op not in {"source", "claim"}:
            raise ValueError("EVENT_OP")
        common = {"tenant", "op", "id", "revision", "content_sha256", "expires_at", "read_allowed"}
        expected = common | ({"supports"} if op == "claim" else set())
        if set(event) != expected:
            raise ValueError("NODE_SCHEMA")
        key = identifier(event["id"])
        if key in nodes:
            raise ValueError("IMMUTABLE_NODE_ID_REUSED")
        pin(event["revision"])
        if type(event["content_sha256"]) is not str or not re.fullmatch(r"[a-f0-9]{64}", event["content_sha256"]):
            raise ValueError("CONTENT_DIGEST")
        integer(event["expires_at"])
        if type(event["read_allowed"]) is not bool:
            raise ValueError("RIGHTS_MUST_BE_EXPLICIT_BOOL")
        if op == "claim":
            groups = event["supports"]
            if type(groups) is not list or not 1 <= len(groups) <= 8:
                raise ValueError("SUPPORT_ALTERNATIVE_BUDGET")
            seen = set()
            for group in groups:
                if type(group) is not list or not 1 <= len(group) <= 8:
                    raise ValueError("SUPPORT_TERM_BUDGET")
                if any(type(x) is not str for x in group) or len(set(group)) != len(group):
                    raise ValueError("SUPPORT_DUPLICATE_OR_TYPE")
                term = tuple(sorted(group))
                if term in seen:
                    raise ValueError("DUPLICATE_SUPPORT_TERM")
                seen.add(term)
                for parent in group:
                    identifier(parent)
                    if parent not in nodes or nodes[parent]["tenant"] != tenant:
                        raise ValueError("SUPPORT_MUST_REFERENCE_EARLIER_SAME_TENANT_NODE")
        # Earlier-node references give a decreasing insertion-rank DAG. No BFT claim.
        nodes[key] = event.copy()
    return nodes, withdrawn


class SupportMemory:
    """Transactional, local research ledger; caller-provided authorization is trusted.

    Hashes only detect changes relative to a retained trusted head. They are not
    signatures. A caller with write access to this DB can rewrite the whole chain.
    """
    def __init__(self, path: Path):
        self.db = sqlite3.connect(str(path), isolation_level=None, timeout=0.1)
        self.db.execute("CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL, previous TEXT NOT NULL, hash TEXT NOT NULL UNIQUE)")

    def close(self) -> None:
        self.db.close()

    def _events(self) -> tuple[list[dict], str]:
        rows = self.db.execute("SELECT seq,payload,previous,hash FROM events ORDER BY seq LIMIT ?", (MAX_EVENTS + 1,)).fetchall()
        if len(rows) > MAX_EVENTS:
            raise ValueError("LEDGER_BUDGET")
        previous, out = ZERO, []
        for i, (seq, payload, prior, checksum) in enumerate(rows, 1):
            value = strict_load(payload)
            if seq != i or prior != previous or checksum != digest({"seq": i, "previous": prior, "event": value}):
                raise ValueError("LEDGER_INTEGRITY")
            out.append(value)
            previous = checksum
        _reduce(out)
        return out, previous

    def head(self) -> str:
        return self._events()[1]

    def apply(self, events: list[dict], *, expected_head: str, principal: str,
              authorize: Callable[[str, str, str], bool]) -> str:
        identifier(principal)
        if type(expected_head) is not str or not re.fullmatch(r"[0-9a-f]{64}", expected_head):
            raise ValueError("EXPECTED_HEAD")
        if type(events) is not list or not 1 <= len(events) <= 64:
            raise ValueError("BATCH_BUDGET")
        # Round-trip to avoid caller mutations racing the transaction.
        if len(canonical(events)) > 131072:
            raise ValueError("EVENT_BYTE_BUDGET")
        copied = [strict_load(canonical(e).decode()) for e in events]
        self.db.execute("BEGIN IMMEDIATE")
        try:
            existing, head = self._events()
            if head != expected_head:
                raise ValueError("STALE_WRITER_HEAD")
            if len(existing) + len(copied) > MAX_EVENTS:
                raise ValueError("LEDGER_BUDGET")
            for event in copied:
                tenant = identifier(event.get("tenant"))
                if authorize(principal, tenant, "append") is not True:
                    raise PermissionError("APPEND_DENIED")
            _reduce(existing + copied)  # Validate all events before writing any.
            for seq, event in enumerate(copied, len(existing) + 1):
                new_head = digest({"seq": seq, "previous": head, "event": event})
                self.db.execute("INSERT INTO events VALUES (?,?,?,?)", (seq, canonical(event).decode(), head, new_head))
                head = new_head
            self.db.execute("COMMIT")
            return head
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def handles(self, *, tenant: str, principal: str, now: int,
                authorize: Callable[[str, str, str], bool], expected_head: str | None = None) -> dict:
        identifier(tenant)
        identifier(principal)
        integer(now)
        if authorize(principal, tenant, "read") is not True:
            raise PermissionError("READ_DENIED")
        events, head = self._events()
        if expected_head is not None and expected_head != head:
            raise ValueError("STALE_READ_HEAD")
        nodes, withdrawn = _reduce(events)
        states, handles = {}, []
        for key, node in nodes.items():
            if node["tenant"] != tenant:
                continue
            if key in withdrawn:
                status = "WITHDRAWN"
            elif node["read_allowed"] is not True:
                status = "RIGHTS_UNAVAILABLE"
            elif now >= node["expires_at"]:
                status = "EXPIRED"
            elif node["op"] == "source":
                status = "SUPPORTED"
            else:
                status = "SUPPORTED" if any(all(states[p] == "SUPPORTED" for p in term)
                                            for term in node["supports"]) else "UNSUPPORTED"
            states[key] = status
            handles.append({"id": key, "revision": node["revision"], "content_sha256": node["content_sha256"],
                            "support_state": status})
        return {"schema": "szl.boundary-support-view/v0.2", "tenant": tenant, "head": head,
                "as_of_epoch_seconds": now, "handles": handles, "truth_verified": False,
                "execution_authority": False, "training_authority": False,
                "note": "Caller-supplied clock and policy; external hydration must recheck this head at use."}
