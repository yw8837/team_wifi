// Only indexable public group-buy pages go through this worker.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    let path;
    if (url.pathname === '/groupbuys/sitemap.xml') {
      path = '/release/groupbuy-pages/sitemap.xml';
    } else if (/^\/groupbuys\/sitemaps\/[^/]+$/.test(url.pathname)) {
      path = '/release/groupbuy-pages/sitemaps/' + url.pathname.split('/').pop();
    } else if (/^\/groupbuys\/[^/]+\/public$/.test(url.pathname)) {
      path = '/release' + url.pathname;
    } else {
      return env.ASSETS.fetch(request);
    }
    if (!['GET', 'HEAD'].includes(request.method)) {
      return new Response('Method not allowed', { status: 405, headers: { Allow: 'GET, HEAD' } });
    }
    try {
      const base = new URL(env.PUBLIC_API_BASE);
      if (base.protocol !== 'https:' || base.username || base.password || base.search || base.hash) {
        throw new Error('Invalid public API base');
      }
      const response = await fetch(base.href.replace(/\/$/, '') + path, {
        method: request.method,
        headers: { Accept: 'text/html, application/xml' },
        redirect: 'manual',
        signal: AbortSignal.timeout(15000),
      });
      const headers = new Headers(response.headers);
      headers.delete('set-cookie');
      headers.set('Cache-Control', 'no-store');
      headers.set('X-Content-Type-Options', 'nosniff');
      headers.set('X-Frame-Options', 'DENY');
      return new Response(response.body, { status: response.status, headers });
    } catch {
      return new Response('잠시 후 다시 시도해 주세요.', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
      });
    }
  },
};
