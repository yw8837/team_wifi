import { pathToFileURL } from 'node:url';

async function get(url, type) {
  const response = await fetch(url, {
    headers: { Accept: type }, redirect: 'error', signal: AbortSignal.timeout(60_000),
  });
  if (!response.ok) throw Error('HTTP ' + response.status);
  if (!response.headers.get('content-type')?.includes(type)) throw Error('Unexpected response type');
  return type === 'application/json' ? response.json() : response.text();
}

// Run against each API origin before switching traffic. Anonymous reads only.
export async function checkCatalogue(base, webOrigin) {
  const results = [];
  async function check(name, fn) {
    try { const value = await fn(); results.push({check:name, ok:true}); return value; }
    catch (error) { results.push({check:name, ok:false, reason:error.message}); }
  }
  await check('public configuration', async () => {
    const config = await get(base + '/config', 'application/json');
    if (config.public_release !== true || config.beta_mode !== false) throw Error('Unexpected release mode');
  });
  const item = await check('live seller catalogue', async () => {
    const page = await get(base + '/release/groupbuys?status=active&limit=20&offset=0', 'application/json');
    const first = page.items.find(row => row.status === 'active' && row.seller_url?.startsWith('https://'));
    if (!first || !first.id) throw Error('No active seller link');
    return first;
  });
  if (item) {
    const path = '/release/groupbuys/' + encodeURIComponent(item.id);
    await check('product details and image source fields', async () => {
      const detail = await get(base + path, 'application/json');
      if (detail.id !== item.id || detail.seller_url !== item.seller_url || !detail.title ||
          !Object.hasOwn(detail,'source_type') || !Object.hasOwn(detail,'is_demo')) throw Error('Incompatible detail schema');
    });
    await check('public product HTML', async () => {
      const html = await get(base + path + '/public','text/html');
      if (!/<h1>[^<]+<\/h1>/.test(html) || !html.includes('판매처에서 현재 조건 확인')) throw Error('Missing product content');
    });
  }
  await check('browser access from production web', async () => {
    const response = await fetch(base + '/config', {method:'OPTIONS', redirect:'error',
      headers:{ Origin:webOrigin, 'Access-Control-Request-Method':'GET', 'Access-Control-Request-Headers':'x-moduyuga-client' },
      signal:AbortSignal.timeout(15_000)});
    if (!response.ok || response.headers.get('access-control-allow-origin') !== webOrigin) throw Error('CORS preflight HTTP ' + response.status);
  });
  return results;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [base,web] = process.argv.slice(2);
  if (!base || !web) throw Error('Usage: node scripts/check-public-catalogue.mjs <https-api-base> <https-web-origin>');
  const results = await checkCatalogue(base.replace(/\/$/,''),new URL(web).origin);
  console.log(JSON.stringify(results,null,2));
  if (results.some(result=>!result.ok)) process.exitCode = 1;
}
