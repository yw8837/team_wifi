const SELLER_HOSTS = new Set([
  'somi9726.cafe24.com', 'poled.co.kr', 'upang.co.kr',
  'www.doctornoah.net', 'www.gonggan27.com', 'www.aguardmall.com',
  'joonie.kr', 'durimall.co.kr', 'oa-mall.co.kr', 'creestyle.com', 'luciroda101.cafe24.com',
  'm.yomimonshop.com', 'preorderbebe.cafe24.com', 'bellamama.cafe24.com',
  'careprin.co.kr', 'misoda.kr', 'verynature.co.kr',
]);

export function sellerPreviewUrl(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return null;
    // The storefront selects its layout by device. Fetch images from its stable mobile page.
    if (url.hostname === 'yomimonshop.com') url.hostname = 'm.yomimonshop.com';
    if (url.hostname === 'minkang1.celebrity.place') {
      return url.pathname === '/m/goods/content.asp'
        && url.searchParams.size === 2
        && ['gc', 'guid'].every(k => /^[1-9][0-9]{0,11}$/.test(url.searchParams.get(k) || '')) ? url : null;
    }
    if (url.hostname === 'shop.srookpay.com') {
      return /^\/luxiai\/Detail\/SLU[0-9]+$/.test(url.pathname) && !url.search ? url : null;
    }
    if (url.hostname === 'sharequeens.store') {
      return /^\/minihome\/(?:wlsdud6580|risa0826)\/product\/[1-9][0-9]{0,10}$/.test(url.pathname) && !url.search ? url : null;
    }
    if (!SELLER_HOSTS.has(url.hostname)) return null;
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
    if (new URL(source).hostname === 'sharequeens.store') {
      const params = url.searchParams;
      return url.origin === 'https://sharequeens.store' && !url.username && !url.password
        && url.pathname === '/img/thumb' && params.size === 3
        && /^\/uploads\/products\/[a-zA-Z0-9_-]+\.(?:webp|png|jpe?g)$/i.test(params.get('src') || '')
        && params.get('w') === '900' && params.get('format') === 'jpeg' ? url.href : null;
    }
    if (new URL(source).hostname === 'minkang1.celebrity.place') {
      if (host !== 'minkang1.celebrity.place' || !/^\/data\/inflz\/goods\/[^/]+\/big\//.test(url.pathname)) return null;
    }
    const trusted = SELLER_HOSTS.has(host) || host === 'aguardmall.com' || host === 'minkang1.celebrity.place' && new URL(source).hostname === host
      || host === 'cdn.imweb.me' || host === 'cafe24img.poxo.com' || host === 'cafe24.poxo.com'
      || host === 'ecimg.cafe24img.com'
      || (host === 'img.srookpay.com' && url.pathname.startsWith('/data/goods/luxiai/'));
    if (url.protocol !== 'https:' || url.username || url.password || url.port || !trusted
        || /(?:logo|favicon|banner)/i.test(url.pathname)) return null;
    return url.href;
  } catch {
    return null;
  }
}

export async function fetchSellerPage(source, init, fetchPage = fetch) {
  const options = { ...init, redirect: 'manual' };
  const response = await fetchPage(source.href, options);
  if (source.hostname !== 'sharequeens.store' || ![301, 302, 303, 307, 308].includes(response.status)) return response;
  const location = response.headers.get('Location');
  if (!location) return response;
  const target = new URL(location, source);
  if (target.origin !== source.origin || target.pathname !== source.pathname || target.username || target.password
      || target.searchParams.size !== 1 || !/^[A-Za-z0-9_.-]{1,1200}$/.test(target.searchParams.get('market_ref') || '')) return response;
  await response.body?.cancel();
  return fetchPage(target.href, options);
}

async function sellerPreview(request, url, context, env) {
  if (!['GET', 'HEAD'].includes(request.method)) {
    return new Response(null, { status: 405, headers: { Allow: 'GET, HEAD' } });
  }
  const source = sellerPreviewUrl(url.searchParams.get('source'));
  if (!source) return new Response(null, { status: 400 });
  // Verified build snapshots avoid browser dependence on seller/CDN availability.
  if (env.ASSETS) {
    const manifestResponse = await env.ASSETS.fetch(new Request(new URL('/seller-images.json', url)));
    if (manifestResponse.ok && manifestResponse.headers.get('content-type')?.includes('json')) {
      const manifest = await manifestResponse.json();
      const path = manifest[source.href]?.path;
      if (/^\/seller-images\/[a-f0-9]{64}\.(jpg|png|webp|gif|avif)$/.test(path || '')) {
        const snapshot = await env.ASSETS.fetch(new Request(new URL(path, url)));
        if (snapshot.ok && snapshot.headers.get('content-type')?.startsWith('image/')) return snapshot;
      }
    }
  }
  const cacheKey = new Request(url.href, { method: 'GET' });
  const cached = await caches.default.match(cacheKey);
  if (cached) return cached;
  try {
    const response = await fetchSellerPage(source, {
      headers: { Accept: 'text/html', 'User-Agent': 'ModuYuga-SourceCheck/1.0' },
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok || !response.headers.get('content-type')?.includes('text/html')) {
      await response.body?.cancel();
      return new Response(null, { status: response.status === 404 || response.status === 410 ? 404 : 502,
        headers: { 'Cache-Control': 'no-store', 'X-Preview-Source-Status': String(response.status) } });
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
    const useGallery = source.hostname === 'minkang1.celebrity.place';
    await new HTMLRewriter().on(useGallery ? 'img[src]' : 'meta[property="og:image"]', {
      element(element) {
        const candidate = productImageUrl(element.getAttribute(useGallery ? 'src' : 'content'), source.href);
        if (candidate && !image) image = candidate;
      },
    }).transform(html).text();
    if (!image) return new Response(null, { status: 404, headers: { 'Cache-Control': 'no-store', 'X-Preview-Error': 'image-metadata-missing' } });
    const imageResponse = await fetch(image, {
      redirect: 'manual', signal: AbortSignal.timeout(10000),
      headers: { Accept: 'image/avif,image/webp,image/png,image/jpeg,image/gif' },
    });
    const imageType = imageResponse.headers.get('content-type')?.split(';')[0];
    if (!imageResponse.ok || !['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif'].includes(imageType)) {
      await imageResponse.body?.cancel();
      return new Response(null, { status: 502 });
    }
    const imageReader = imageResponse.body.getReader();
    const imageChunks = [];
    let imageSize = 0;
    while (true) {
      const { done, value } = await imageReader.read();
      if (done) break;
      imageSize += value.length;
      if (imageSize > 5_000_000) {
        await imageReader.cancel();
        return new Response(null, { status: 413 });
      }
      imageChunks.push(value);
    }
    const preview = new Response(new Blob(imageChunks), {
      headers: { 'Content-Type': imageType, 'Cache-Control': 'public, max-age=3600',
        'X-Content-Type-Options': 'nosniff', 'Access-Control-Allow-Origin': '*' },
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
    if (url.pathname === '/' && request.method === 'GET') {
      const home = await env.ASSETS.fetch(request);
      if (!home.ok || !home.headers.get('Content-Type')?.includes('text/html')) return home;
      const origin = 'https://moduyuga.yeolmaeapps.kr/';
      const schema = JSON.stringify({'@context': 'https://schema.org', '@type': 'WebSite',
        name: '모두의 육아', alternateName: 'ModuYuga', url: origin, inLanguage: 'ko',
        publisher: {'@type': 'Organization', name: 'Team_Wifi'}});
      return new HTMLRewriter().on('head', {element(el) {
        el.append('<meta name="google-site-verification" content="G6iw65W4Gm78r41JUAwpP4me4FM2uJUKnOtm3WYb1fw"><link rel="canonical" href="' + origin + '"><script type="application/ld+json">' + schema + '</script>', {html: true});
      }}).on('#root', {element(el) {
        el.append('<main><h1>모두의 육아</h1><p>모두의 육아(ModuYuga)는 여러 판매처의 육아용품 공동구매 정보를 모아 가격과 배송 조건을 비교하고, 보호자끼리 질문과 후기를 나누는 서비스입니다.</p><h2>공구는 어디에서 구매하나요?</h2><p>상품 상세에서 판매처와 확인된 마감·배송 조건을 살펴본 뒤 판매처에서 주문합니다.</p><h2>기저귀는 어떻게 비교하나요?</h2><p>같은 단계와 규격에서 배송비를 포함한 금액을 총 매수로 나누세요.</p><a href="/guides/diaper-unit-price">기저귀 단가 계산 예시</a> · <a href="/guides">육아템 비교 가이드</a> · <a href="https://play.google.com/store/apps/details?id=kr.moduyuga.app">모두의 육아 Android 앱</a></main>', {html:true});
      }}).transform(home);
    }
    if (url.pathname === '/groupbuys/preview-image') return sellerPreview(request, url, context, env);
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
    const publicDetailFallback = () => {
      if (request.method !== 'GET' || !url.pathname.endsWith('/public') ||
          !request.headers.get('Accept')?.includes('text/html')) return null;
      return new Response(null, {status:302, headers:{
        Location:url.pathname.slice(0,-'/public'.length), 'Cache-Control':'no-store',
      }});
    };
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
      if (response.status >= 500) {
        const fallback = publicDetailFallback();
        if (fallback) return fallback;
      }
      const headers = new Headers(response.headers);
      headers.delete('set-cookie');
      headers.set('Cache-Control', 'no-store');
      headers.set('X-Content-Type-Options', 'nosniff');
      headers.set('X-Frame-Options', 'DENY');
      return new Response(response.body, { status: response.status, headers });
    } catch {
      return publicDetailFallback() ?? new Response('잠시 후 다시 시도해 주세요.', {
        status: 503,
        headers: { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' },
      });
    }
  },
};
