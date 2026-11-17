# Pinned Second Brain owner-mount contract — research only

**Result on 2026-11-17:** The real FastAPI application at
`szl-holdings/szl-second-brain@e4c6031a4e6e111a9c79601eaf8e4d9f24a1b40a`
was imported in an isolated local TestClient process. Ten cross-repository
contracts passed. Its existing `/api/v1/refinement-memory` public handles-only
response was unchanged by mounting a synthetic assurance adapter. The synthetic
SQLite ledger was byte-identical before and after the HTTP session.

## Run the explicit external integration test

```powershell
python -B research/boundary_lab/second_brain_contract.py `
  --owner-checkout C:\exact\pinned\szl-second-brain `
  --out C:\Users\steph\SZL-private-evidence\new-owner-check.json
```

The owner checkout MUST be the **exact, clean** pinned commit above. A moved
default branch, a modified tracked file, or an untracked checkout file fails
closed. The test does not trust a matching commit hash over dirty source bytes. The output filename must not exist. The test uses a
temporary synthetic ledger, not the operational private graph. No persistent
ASGI route, new network listener, model, data export or production credential
is created. `TestClient` is in-process, so it proves local integration
behavior but not hosted reverse-proxy behavior.

## Existing owner and its boundary

Second Brain's `second_brain.web` serves publicly accessible, handles-only
and read-only research routes, including `/api/v1/refinement-memory`. Its
current HTTP app does **not** establish an authenticated principal and
per-object authorization for private assurance evidence. DO NOT mount
`AssuranceASGI` there with a fabricated identity or public identity headers.
The synthetic test resolver is a Python closure controlled by the test runner;
it is **not** deployable authorization middleware.

The canonical Second Brain app and its `routes_refinement` route remain
unchanged. No changes are made to Hatun's canonical MCP catalog, A11oy, Anatomy,
locked formulas or prior registered source. `lean-rlvr-proving-ground` owns
this opt-in regression harness as a research consumer of the existing v0.3
AssuranceASGI contract. This is not a new watcher.

## Observed controls

1. Public refinement route unchanged.
2. Forged principal/tenant HTTP headers cannot authorize access.
3. An untrusted cross-tenant context is denied.
4. Trusted **synthetic** Context serves the declared test fixture.
5. Rehearsal invalidates the A-only conclusion while preserving A-OR-B.
6. Stale If-Match head is rejected.
7. Expired trusted head is unavailable.
8. Revoked in-process identity is denied on the next call.
9. POST is forbidden.
10. Original SQLite bytes are unchanged.

## Release gate before *any* live owner wiring

A real owner must supply and independently test a principal from its existing
authentication session, a tenant-aware per-object policy, external retained
anchor custody and policy revision, trusted time, a reviewed mount path and
reverse proxy rules. An arbitrary header or the test resolver is never such an
owner. Denied tenants and unknown sources must not leak metadata. A status 200
from a public page proves only page reachability.

The gates remain explicit: external anchor readback, live identity, manual
security review, browser-rendered acceptance, deployed revision and rollback,
independent holdout and any production qualification. The harness's 10 checks
do not satisfy those gates. No host code is modified or deployed.

At v0.3, the hypothetical support state is computed by the authoritative
full replay. The standalone incremental candidate was slower on a synthetic
128-node measurement and is NOT activated in the service.
