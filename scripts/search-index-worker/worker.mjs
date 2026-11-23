const origin = 'https://moduyuga.yeolmaeapps.kr';
const ownershipKey = 'c70b27f9540e408d84d201bbd264a1cc';

async function read(url) {
  const parsed = new URL(url);
  if (parsed.origin !== origin || parsed.search || parsed.hash || parsed.username || parsed.password) throw Error('Invalid public URL');
  const response = await fetch(url, {headers:{'User-Agent':'ModuYuga-IndexCheck/1.0'}, redirect:'error', signal:AbortSignal.timeout(18000)});
  if (!response.ok) throw Error('Failed to read ' + parsed.pathname + ' (' + response.status + ')');
  return response.text();
}

async function catalogue(path, depth = 0) {
  const xml = await read(path);
  if (depth > 2 || !/<(?:urlset|sitemapindex)[\s>]/.test(xml)) throw Error('Invalid public sitemap');
  const entries = [];
  for (const [, tag, body] of xml.matchAll(/<(sitemap|url)>([\s\S]*?)<\/\1>/g)) {
    const url = /<loc>([^<]+)<\/loc>/.exec(body)?.[1];
    if (!url?.startsWith(origin + '/')) throw Error('Unexpected sitemap URL');
    if (tag === 'sitemap') entries.push(...await catalogue(url, depth + 1));
    else {
      const stamp = /<lastmod>([^<]+)<\/lastmod>/.exec(body)?.[1];
      if (stamp && url.startsWith(origin + '/groupbuys/')) entries.push([url, stamp]);
      else {
        const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(await read(url)));
        entries.push([url, Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2,'0')).join('')]);
      }
    }
  }
  return entries;
}

export async function notifyChanges(env) {
  const current = Object.fromEntries([...await catalogue(origin + '/sitemap.xml'), ...await catalogue(origin + '/groupbuys/sitemap.xml')]);
  if (!Object.hasOwn(current, origin + '/')) throw Error('Incomplete sitemap');
  const old = await env.STATE.get('index', 'json') ?? {};
  const changed = [...new Set([...Object.keys(current), ...Object.keys(old)])].filter(url => current[url] !== old[url]);
  if (changed.length) {
    for (let offset = 0; offset < changed.length; offset += 10000) {
      const response = await fetch('https://api.indexnow.org/indexnow', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({host:new URL(origin).host, key:ownershipKey, urlList:changed.slice(offset,offset+10000)}),
      });
      if (![200,202].includes(response.status)) throw Error('IndexNow ' + response.status);
    }
    await env.STATE.put('index', JSON.stringify(current));
  }
  const summary = {checked_at:new Date().toISOString(), pages:Object.keys(current).length, submitted:changed.length};
  await env.STATE.put('last-run', JSON.stringify(summary));
  return summary;
}
// Check the same public product document a visitor opens. A static home page can stay
// healthy throughout an origin outage. Keep health checks separate from indexing.
export async function checkPublicProduct(env) {
  const checked_at = new Date().toISOString();
  try {
    const xml = await read(origin + '/groupbuys/sitemaps/1');
    const path = /<loc>([^<]+\/groupbuys\/[a-f0-9-]{36}\/public)<\/loc>/.exec(xml)?.[1];
    if (!path) throw Error('No public product in sitemap');
    const page = await read(path);
    if (!/<h1>[^<]+<\/h1>/.test(page) || !page.includes('판매처에서 현재 조건 확인')) throw Error('Missing product or seller link');
    await env.STATE.put('catalogue-health', JSON.stringify({checked_at, ok:true, product:path}));
  } catch (error) {
    await env.STATE.put('catalogue-health', JSON.stringify({checked_at, ok:false, error:error.message}));
    throw error;
  }
}
export default {async scheduled(event, env) {
  if (event.cron === '*/10 * * * *') await checkPublicProduct(env);
  else await notifyChanges(env);
}};
