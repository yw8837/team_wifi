const SELLER_HOSTS = new Set([
  'somi9726.cafe24.com', 'poled.co.kr', 'upang.co.kr',
  'www.doctornoah.net', 'www.gonggan27.com', 'www.aguardmall.com',
]);

export function sellerPreviewUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port
        || !SELLER_HOSTS.has(url.hostname)) return null;
    const cafeProduct = url.pathname === '/product/detail.html'
      && /^\d+$/.test(url.searchParams.get('product_no') || '');
    const imwebProduct = /^\/shop_view\/?$/.test(url.pathname)
      && /^\d+$/.test(url.searchParams.get('idx') || '');
    return cafeProduct || imwebProduct ? url : null;
  } catch {
    return null;
  }
}

export function productImageUrl(value, source) {
  try {
    if (!value) return null;
    const url = new URL(value, source);
    const host = url.hostname;
    const trusted = SELLER_HOSTS.has(host) || host === 'aguardmall.com'
      || host === 'cdn.imweb.me' || host === 'cafe24img.poxo.com'
      || host === 'ecimg.cafe24img.com';
    if (url.protocol !== 'https:' || url.username || url.password || url.port || !trusted
        || /(?:logo|favicon|banner)/i.test(url.pathname)) return null;
    return url.href;
  } catch {
    return null;
  }
}

async function sellerPreview(request, url, context) {
  if (!['GET', 'HEAD'].includes(request.method)) {
    return new Response(null, { status: 405, headers: { Allow: 'GET, HEAD' } });
  }
  const source = sellerPreviewUrl(url.searchParams.get('source'));
  if (!source) return new Response(null, { status: 400 });
  const cacheKey = new Request(url.href, { method: 'GET' });
  const cached = await caches.default.match(cacheKey);
  if (cached) return cached;
  try {
    const response = await fetch(source.href, {
      headers: { Accept: 'text/html', 'User-Agent': 'ModuYuga-SourceCheck/1.0' },
      redirect: 'manual',
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok || !response.headers.get('content-type')?.includes('text/html')) {
      await response.body?.cancel();
      return new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store' } });
    }
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 2_000_000) {
        await reader.cancel();
        return new Response(null, { status: 413 });
      }
      chunks.push(value);
    }
    let image = null;
    const html = new Response(new Blob(chunks), { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    await new HTMLRewriter().on('meta[property="og:image"]', {
      element(element) {
        const candidate = productImageUrl(element.getAttribute('content'), source.href);
        if (candidate) image = candidate;
      },
    }).transform(html).text();
    if (!image) return new Response(null, { status: 404 });
    const preview = new Response(null, {
      status: 302,
      headers: { Location: image, 'Cache-Control': 'public, max-age=3600', 'Referrer-Policy': 'no-referrer' },
    });
    context.waitUntil(caches.default.put(cacheKey, preview.clone()));
    return preview;
  } catch {
    return new Response(null, { status: 502, headers: { 'Cache-Control': 'no-store' } });
  }
}

export default {
  async fetch(request, env, context) {
    const url = new URL(request.url);
    if (url.pathname === '/groupbuys/preview-image') return sellerPreview(request, url, context);
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
