import { mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { sellerPreviewUrl, productImageUrl } from './cloudflare-public-worker.mjs';

const [apiBase, output] = process.argv.slice(2);
if (!apiBase?.startsWith('https://') || !output) throw new Error('API origin and output directory required');
const response = await fetch(apiBase + '/release/groupbuys?status=active&limit=100');
if (!response.ok) throw new Error('Public catalogue unavailable');
const { items } = await response.json();
const manifest = {};
const failures = [];
await mkdir(join(output, 'seller-images'), { recursive: true });
for (const item of items) {
  const source = sellerPreviewUrl(item.seller_url);
  if (!source || item.is_demo || item.source_type !== 'seller_page') continue;
  try {
    const page = await fetch(source, { redirect: 'error', signal: AbortSignal.timeout(15000) });
    if (!page.ok) throw new Error('Seller status ' + page.status);
    const html = await page.text();
    let image;
    for (const tag of html.match(/<meta\b[^>]*>/gi) || []) {
      const attrs = Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*(["'])(.*?)\2/gs)]
        .map(match => [match[1].toLowerCase(), match[3].replaceAll('&amp;', '&')]));
      if (attrs.property === 'og:image') image = productImageUrl(attrs.content, source) || image;
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
