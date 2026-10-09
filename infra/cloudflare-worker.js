/**
 * Gmail Manager same-origin gateway.
 * /api/* -> Render FastAPI
 * /*     -> Render static React build (SPA fallback).
 * This prevents cross-domain CSRF and OAuth-cookie failures.
 */
const API_ORIGIN = "https://gmail-manager-api.onrender.com";
const WEB_ORIGIN = "https://gmail-manager-web.onrender.com";

addEventListener("fetch", event => {
  event.respondWith(handleRequest(event.request));
});

async function handleRequest(request) {
  const incoming = new URL(request.url);
  const isApi = incoming.pathname === "/api" || incoming.pathname.startsWith("/api/");
  const forwardedPath = isApi ? (incoming.pathname.slice(4) || "/") : incoming.pathname;
  const origin = isApi ? API_ORIGIN : WEB_ORIGIN;
  const target = new URL(forwardedPath + incoming.search, origin);

  try {
    const headers = new Headers(request.headers);
    headers.delete("host");
    const upstream = new Request(target.toString(), {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual"
    });

    let response = await fetch(upstream);
    if (!isApi && response.status === 404 && request.method === "GET"
        && !forwardedPath.split("/").pop().includes(".")
        && (request.headers.get("accept") || "").includes("text/html")) {
      response = await fetch(new URL("/index.html", WEB_ORIGIN), {redirect: "manual"});
    }

    const outgoingHeaders = new Headers(response.headers);
    if (isApi) outgoingHeaders.set("cache-control", "no-store");
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: outgoingHeaders
    });
  } catch {
    return new Response("Gmail Manager is temporarily unavailable", {
      status: 502,
      headers: {"content-type": "text/plain", "cache-control": "no-store"}
    });
  }
}
