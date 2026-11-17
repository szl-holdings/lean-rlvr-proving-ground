# Boundary Assurance v0.3 — connected research slice

Status: **LOCAL RESEARCH INTEGRATION; NOT DEPLOYED TO A11OY, BRAIN, ANATOMY OR HATUN.**

This additive slice connects the existing v0.2 SQLite support ledger to one bounded
read API, a browser interface, and an ASGI mount adapter. It is not another agent,
training controller, watcher or memory service. No private graph content is loaded.
The frontend consumes backend evaluations; it does not decide source truth, identity,
policy, tenant, observation time, or execution authority.

## Source boundary

Parent proposal: `szl-holdings/lean-rlvr-proving-ground` PR #6,
`a78b44a8b1297320bdcb1d24164cf09abe5dc28f` (merged in a subsequent source readback before this integration proposal).
The v0.2 core is reused byte-for-byte, pinned by SHA-256
`7dfdc9419b210a146a06b0839deff299117496f07eff882d292c1c0eb7ad6040`.
A changed core fails closed until this adapter is reviewed against it.
No locked formula or original proof-admission path is changed.

## Data path and authority

Existing owner authentication -> trusted Context -> server object/tenant policy ->
retained controller anchor and clock -> read-only SQLite snapshot -> support
projection / hypothetical removal / bounded cut sets -> same-origin UI.

The owner must supply Context, policy, clock and an independently retained anchor.
An anchor is a previously trusted head, observation time and policy revision. It
is not a signature or independent witness. Do not regenerate a fresh anchor from
the same potentially compromised database on every request and call that independent
verification. Bind a policy change to a new policy revision atomically in the owner.
The clock's trust and synchronization remain an integration responsibility.

Every API call opens SQLite in read-only mode with query_only enabled. Database
schema/content writes are impossible on that connection. The WSGI surface accepts
GET only. The allowed paths are `/`, `/assurance.css`, `/assurance.mjs`,
`/api/snapshot`, `/api/scenario` and `/api/cuts`. It never accepts arbitrary file paths,
upstream URLs, code, tenant, principal, policy or clock values from the browser.

Scenario and cut-set calls require the exact current head in If-Match. All requests
check anchor freshness, exact ledger continuity and current policy. A stale view is
409; a missing precondition 428; unavailable evidence 503. Error payloads disclose
no raw exceptions, credentials, file paths, graph bytes or hidden object identities.
Unviewable dependencies redact the whole explanation, including support terms.

The browser verifies the response digest, exact contract and false authority flags.
It clears previous usable state before a request, rejects late older responses,
charges request latency against validity, and clears evidence at expiry. No browser
storage, third-party script, external font, raw HTML interpolation or wildcard CORS
is used. CSP restricts script/style/connect to self and disallows embedding.
An actual click/operation must still revalidate in the action owner: this component
never grants execution authority, and a read snapshot is not distributed fencing.

Bounds: 2,048 ledger events / 4 MiB payload, 128 nodes, 8 requested withdrawals,
2 KiB query, 256 KiB JSON response, at most 256 cut-set candidates and width <=3
for the public endpoint. Pruned candidates also consume the search budget.

## What the failure sets mean

For a claim supported by A OR B, neither single withdrawal removes support; {A,B}
does. For A AND B, {A} and {B} are minimal failure sets. The calculation uses exact
version-bound declared dependencies. It does not infer causality, discover omitted
edges, measure probabilities, or show that an underlying statement is factually true.
When width or candidate budgets exclude part of the search, the result is explicitly
BOUNDED_PARTIAL, even when some witnesses are found. No global-minimality claim follows.
The inspected source graph is finite; the client cannot add a heuristic edge and
silently promote it into a logical prerequisite.

## Existing estate integration points inspected

- `a11oy/a11oy_brain_graph.py` at `8e31409245f6223dda6bb9784fbcbefd5f9892de`
  contains token-associated links and a 2026-07-07 static repository snapshot.
  Keep that exploratory graph distinct from admitted support dependencies. A source
  code read is not proof of what a hosted deployment currently renders.
- `szl-second-brain/second_brain/routes_refinement.py` at
  `1647f07cb9bd4b9b3e23efe6fb5b3388144116e6` already defines a handles-only
  `/api/v1/refinement-memory` route. Preserve its ownership, unavailable responses
  and no-execution/no-training boundary rather than introducing a competing writer.
- `hatun-mcp/README.md` was read on the default branch during this pass. Its canonical
  Python gateway owns authentication, catalog and Streamable HTTP. Its product page
  is explicitly not deployment proof, and its old standalone HF publisher must not
  be recreated. A future read tool must use that existing authenticated catalog.
  No such tool was registered in this pass.
- PR #5 owns referee/admission changes and was merged before this proposal. Its
  paths were not modified. No checkout-action update or approval bypass is included.

## Mount through the current owner, not a new public service

The ASGI adapter has no listener and requires a trusted in-process identity resolver:

```python
from assurance_asgi import AssuranceASGI
# service: AssuranceService constructed with owner-controlled ledger/anchor/policy.
# resolve_context: returns Context ONLY from the owner's validated authentication.
owner_app.mount('/assurance', AssuranceASGI(service, resolve_context))
```

The concrete live authentication mapping, controller anchor channel, object policy,
allowed source class, reverse-proxy mount path and frontend navigation require their
existing owners' admission. An arbitrary `X-Principal` header is not an identity.
The demonstration resolver in `assurance_demo_server.py` is explicitly synthetic and
must never be used to authenticate real content. A public deployment needs the
owner's existing TLS/authentication, observability and lifecycle infrastructure.

## Reproduce

```sh
python -B -m unittest -v
node --test assurance_web/client.test.mjs
python assurance_demo_server.py --out /a/new/private/demo-directory --seconds 60
```

The demo binds one ephemeral loopback port for at most 120 seconds, uses synthetic
sources, rejects unexpected Host headers, and shuts down its own server. It does
not start a persistent scheduler or touch unrelated serving processes. The CLI's
local URL is printed for that session only.

`check_fastapi_mount.py` in the delivery root separately checks compatibility with
installed FastAPI/Starlette without modifying an estate app. Python socket tests
exercise actual HTTP requests. Node tests exercise frontend validation and races.
Browser-rendered acceptance is a separate gate: local Chromium navigation was
blocked by administrator policy during this pass; no browser policy was changed.

## Outstanding gates

Source admission and browser-rendered interaction tests;
real principal/policy integration; externally retained/witnessed anchors; owner-led
UI navigation/mount deployment; operational telemetry readback; adversarial review;
independent sealed model experiment; source/dataset rights; Python-to-Lean refinement.
No test count is a model accuracy score or a production-readiness percentage.
