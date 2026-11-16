import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { sellerPreviewUrl, productImageUrl } from './cloudflare-public-worker.mjs';

test('preview fetches only reviewed HTTPS product pages', () => {
  assert.ok(sellerPreviewUrl('https://poled.co.kr/product/detail.html?product_no=662'));
  assert.ok(sellerPreviewUrl('https://www.doctornoah.net/shop_view?idx=545'));
  for (const url of [
    'https://127.0.0.1/product/detail.html?product_no=1',
    'https://poled.co.kr.attacker.example/product/detail.html?product_no=1',
    'https://user:pass@poled.co.kr/product/detail.html?product_no=1',
    'http://poled.co.kr/product/detail.html?product_no=1',
    'https://poled.co.kr/admin',
    'https://poled.co.kr:8080/product/detail.html?product_no=1',
  ]) assert.equal(sellerPreviewUrl(url), null);
});

test('preview accepts product CDN images and excludes logo or unsafe destinations', () => {
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
