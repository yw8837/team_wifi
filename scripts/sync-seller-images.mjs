import { mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { sellerPreviewUrl, productImageUrl, fetchSellerPage } from './cloudflare-public-worker.mjs';

const [apiBase, output] = process.argv.slice(2);
if (!apiBase?.startsWith('https://') || !output) throw new Error('API origin and output directory required');
const items = [];
for (let offset = 0; ; offset += 100) {
  const response = await fetch(apiBase + '/release/groupbuys?status=all&limit=100&offset=' + offset);
  if (!response.ok) throw new Error('Public catalogue unavailable');
  const page = await response.json();
  items.push(...page.items);
  if (!page.has_more) break;
  if (!page.items.length || offset >= 10000) throw new Error('Incomplete public catalogue');
}
const manifest = {};
const failures = [];
await mkdir(join(output, 'seller-images'), { recursive: true });
for (const item of items) {
  const source = sellerPreviewUrl(item.seller_url);
  if (!source || item.is_demo || item.source_type !== 'seller_page') continue;
  try {
    const page = await fetchSellerPage(source, { signal: AbortSignal.timeout(15000) });
    if (!page.ok) throw new Error('Seller status ' + page.status);
    const html = await page.text();
    let image;
    const useGallery = source.hostname === 'minkang1.celebrity.place';
    for (const tag of html.match(useGallery ? /<img\b[^>]*>/gi : /<meta\b[^>]*>/gi) || []) {
      const attrs = Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*(["'])(.*?)\2/gs)]
        .map(match => [match[1].toLowerCase(), match[3].replaceAll('&amp;', '&')]));
      if (useGallery || attrs.property === 'og:image') image = productImageUrl(useGallery ? attrs.src : attrs.content, source);
      if (image) break;
    }
    if (!image) throw new Error('No product image');
    const download = await fetch(image, { redirect: 'error', signal: AbortSignal.timeout(15000) });
    const type = download.headers.get('content-type')?.split(';')[0];
    const extension = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/gif': 'gif', 'image/avif': 'avif' }[type];
    if (!download.ok || !extension) throw new Error('Invalid image response');
    const bytes = Buffer.from(await download.arrayBuffer());
    if (bytes.length > 5_000_000) throw new Error('Image exceeds size limit');
    const name = createHash('sha256').update(bytes).digest('hex') + '.' + extension;
    await writeFile(join(output, 'seller-images', name), bytes);
    manifest[source.href] = { path: '/seller-images/' + name, image, checked_at: new Date().toISOString() };
  } catch (error) {
    failures.push({ id: item.id, reason: error.message });
  }
}
await writeFile(join(output, 'seller-images.json'), JSON.stringify(manifest));
console.log(JSON.stringify({ saved: Object.keys(manifest).length, failures }));
if (failures.length) process.exitCode = 1;
