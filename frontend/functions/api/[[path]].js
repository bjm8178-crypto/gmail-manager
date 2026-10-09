/**
 * Same-origin API proxy for Gmail Manager.
 * Cookies, OAuth callback, and CSRF stay on the Pages hostname.
 * Configure BACKEND_ORIGIN as a Pages environment variable.
 */
export async function onRequest({ request, env }) {
  if (!env.BACKEND_ORIGIN) {
    return new Response('Backend not yet configured', { status: 503 });
  }

  let base;
  try {
    base = new URL(env.BACKEND_ORIGIN);
    if (base.protocol !== 'https:' || base.username || base.password || base.search || base.hash) {
      throw new Error('Invalid backend origin');
    }
  } catch {
    return new Response('Invalid backend configuration', { status: 503 });
  }

  const original = new URL(request.url);
  const path = original.pathname.replace(/^\/api(?=\/|$)/, '') || '/';
  const target = new URL(path + original.search, base);
  const headers = new Headers(request.headers);
  headers.delete('host');
  headers.delete('cf-connecting-ip');
  headers.delete('x-forwarded-host');

  try {
    const upstream = await fetch(new Request(target.toString(), {
      method: request.method,
      headers,
      body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
      redirect: 'manual',
    }), { redirect: 'manual' });

    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set('Cache-Control', 'no-store');
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return new Response('Backend temporarily unavailable', {
      status: 502,
      headers: { 'Cache-Control': 'no-store' },
    });
  }
}
