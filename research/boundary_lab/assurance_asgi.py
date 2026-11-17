# SPDX-License-Identifier: Apache-2.0
"""Mount adapter for an existing ASGI owner; no network listener or auth creation.

Example: owner_app.mount('/assurance', AssuranceASGI(service, resolve_context)).
resolve_context must validate the owner's existing authenticated principal and
return Context or None. It must not trust unsigned identity/tenant headers.
"""
import asyncio
import io
from assurance_surface import AssuranceApp, Context


class AssuranceASGI:
    def __init__(self, service, resolve_context):
        if not callable(resolve_context):
            raise TypeError("TRUSTED_CONTEXT_RESOLVER_REQUIRED")
        self.app = AssuranceApp(service)
        self.resolve_context = resolve_context

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            raise ValueError("HTTP_ONLY")
        path = scope.get("path", "")
        root = scope.get("root_path", "")
        if root and path.startswith(root + "/"):
            path = path[len(root):]
        try:
            ctx = self.resolve_context(scope)
        except Exception:
            ctx = None
        if type(ctx) is not Context:
            ctx = None
        # Only a precondition is copied from HTTP headers. Identity is not.
        heads = [v for k,v in scope.get("headers", []) if k.lower() == b"if-match"]
        env = {"REQUEST_METHOD": scope.get("method", ""), "PATH_INFO": path,
               "QUERY_STRING": scope.get("query_string", b"").decode("ascii", errors="replace"),
               "wsgi.input": io.BytesIO(), "szl.assurance.context": ctx}
        if heads:
            env["HTTP_IF_MATCH"] = heads[0].decode("ascii",errors="replace") if len(heads)==1 else "INVALID_DUPLICATE_PRECONDITION"
        response = {}
        def start(status, headers):
            response["status"] = int(status.split()[0])
            response["headers"] = [(k.lower().encode("ascii"),v.encode("ascii")) for k,v in headers]
        def compute():
            return b"".join(self.app(env,start))
        body = await asyncio.to_thread(compute)
        await send({"type":"http.response.start", **response})
        await send({"type":"http.response.body", "body":body})
