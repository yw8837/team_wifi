import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { sellerPreviewUrl, productImageUrl, fetchSellerPage } from './cloudflare-public-worker.mjs';

test('preview fetches only reviewed HTTPS product pages', () => {
  assert.ok(sellerPreviewUrl('https://poled.co.kr/product/detail.html?product_no=662'));
  assert.equal(sellerPreviewUrl('https://yomimonshop.com/product/detail.html?product_no=2965').hostname, 'm.yomimonshop.com');
  assert.ok(sellerPreviewUrl('https://www.doctornoah.net/shop_view?idx=545'));
  assert.ok(sellerPreviewUrl('https://shop.srookpay.com/luxiai/Detail/SLU93540156'));
  for (const url of [
    'https://shop.srookpay.com/other/Detail/SLU93540156',
    'https://127.0.0.1/product/detail.html?product_no=1',
    'https://poled.co.kr.attacker.example/product/detail.html?product_no=1',
    'https://user:pass@poled.co.kr/product/detail.html?product_no=1',
    'http://poled.co.kr/product/detail.html?product_no=1',
    'https://poled.co.kr/admin',
    'https://poled.co.kr:8080/product/detail.html?product_no=1',
  ]) assert.equal(sellerPreviewUrl(url), null);
});

test('preview accepts product CDN images and excludes logo or unsafe destinations', () => {
  const pot = 'https://minkang1.celebrity.place/m/goods/content.asp?gc=1663&guid=783059';
  assert.ok(sellerPreviewUrl(pot));
  assert.equal(sellerPreviewUrl(pot + '&gc=1664'), null);
  assert.equal(productImageUrl('/data/inflz/partner/minkang/imgSNS.gif', pot), null);
  assert.ok(productImageUrl('/data/inflz/goods/wivva1115/big/item.jpg', pot));
  const source = 'https://poled.co.kr/product/detail.html?product_no=662';
  assert.equal(productImageUrl('/web/product/big/item.jpg', source), 'https://poled.co.kr/web/product/big/item.jpg');
  assert.ok(productImageUrl('https://cdn.imweb.me/thumbnail/item.png', source));
  assert.ok(productImageUrl('https://cafe24img.poxo.com/store/web/product/item.jpg', source));
  for (const url of [null, 'https://aguardmall.com/um/logo.png', 'javascript:alert(1)',
    'https://127.0.0.1/private.jpg', 'https://attacker.example/image.jpg']) {
    assert.equal(productImageUrl(url, source), null);
  }
});

test('invalid source and write requests never trigger seller fetch', async () => {
  const url = 'https://moduyuga.yeolmaeapps.kr/groupbuys/preview-image?source=https://localhost/';
  assert.equal((await worker.fetch(new Request(url), {}, {})).status, 400);
  assert.equal((await worker.fetch(new Request(url, { method: 'POST' }), {}, {})).status, 405);
});

test('reviewed mini-store thumbnails use only its local product uploads', () => {
  const source = 'https://sharequeens.store/minihome/wlsdud6580/product/916';
  assert.ok(sellerPreviewUrl(source));
  assert.equal(sellerPreviewUrl(source.replace('wlsdud6580', 'test456')), null);
  assert.equal(sellerPreviewUrl(source + '?market_ref=tracker'), null);
  const thumb = '/img/thumb?src=%2Fuploads%2Fproducts%2Fproduct_v_98.png&w=900&format=jpeg';
  assert.ok(productImageUrl(thumb, source));
  assert.equal(productImageUrl(thumb.replace('%2Fuploads%2Fproducts%2F', 'https://other.example/'), source), null);
  assert.equal(productImageUrl(thumb + '&src=https://other.example/', source), null);
  assert.equal(productImageUrl('https://other.example' + thumb, source), null);
});

test('the mini-store can redirect once to its own product with a market reference', async () => {
  const source = new URL('https://sharequeens.store/minihome/wlsdud6580/product/916');
  for (const [destination, expectedCalls] of [
    ['?market_ref=example.ref', 2], ['/login?market_ref=x', 1], ['//example.org/?market_ref=x', 1],
    ['?market_ref=x&next=other', 1], ['?market_ref=', 1],
  ]) {
    let calls = 0;
    const get = async (_url, options) => {
      assert.equal(options.redirect, 'manual');
      return ++calls === 1 ? new Response(null, { status: 302, headers: { Location: destination } }) : new Response('ok');
    };
    const result = await fetchSellerPage(source, {}, get);
    assert.equal(calls, expectedCalls);
    assert.equal(result.status, expectedCalls === 2 ? 200 : 302);
  }
});

test('uses verified image snapshots without requesting the remote seller', async () => {
  const source = 'https://poled.co.kr/product/detail.html?product_no=662';
  const path = '/seller-images/' + 'a'.repeat(64) + '.jpg';
  const requests = [];
  const env = { ASSETS: { async fetch(request) {
    requests.push(new URL(request.url).pathname);
    if (requests.length === 1) return Response.json({ [source]: { path } });
    return new Response(new Uint8Array([255, 216, 255]), { headers: { 'Content-Type': 'image/jpeg' } });
  } } };
  const response = await worker.fetch(new Request('https://moduyuga.yeolmaeapps.kr/groupbuys/preview-image?source=' + encodeURIComponent(source)), env, {});
  assert.deepEqual(requests, ['/seller-images.json', path]);
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('location'), null);
  assert.equal((await response.arrayBuffer()).byteLength, 3);
});

test('serves image bytes on the same origin without a CSP-blocked redirect', async () => {
  const original = { fetch: globalThis.fetch, caches: globalThis.caches, HTMLRewriter: globalThis.HTMLRewriter };
  const bytes = new Uint8Array([255, 216, 255, 224, 0, 1]);
  const calls = [];
  globalThis.caches = { default: { match: async () => null, put: async () => {} } };
  globalThis.HTMLRewriter = class {
    on(selector, handler) { this.handler = handler; return this; }
    transform() {
      this.handler.element({ getAttribute: () => 'https://poled.co.kr/web/product/big/product.jpg' });
      return new Response('');
    }
  };
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return calls.length === 1
      ? new Response('<html/>', { headers: { 'Content-Type': 'text/html' } })
      : new Response(bytes, { headers: { 'Content-Type': 'image/jpeg' } });
  };
  try {
    const source = encodeURIComponent('https://poled.co.kr/product/detail.html?product_no=662');
    const response = await worker.fetch(new Request('https://moduyuga.yeolmaeapps.kr/groupbuys/preview-image?v=2&source=' + source), {}, { waitUntil() {} });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('location'), null);
    assert.equal(response.headers.get('content-type'), 'image/jpeg');
    assert.deepEqual(new Uint8Array(await response.arrayBuffer()), bytes);
    assert.equal(calls[1].options.redirect, 'manual');
  } finally {
    Object.assign(globalThis, original);
  }
});
