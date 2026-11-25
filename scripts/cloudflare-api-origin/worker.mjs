const apiHost = 'moduyuga-api.yeolmaeapps.kr';
// Keep the public API hostname stable for installed clients. Forward writes once,
// even if the origin response is lost.
export async function routeRecoveryApi(request, send = fetch) {
  const incoming = new URL(request.url);
  if (incoming.hostname !== apiHost || !incoming.pathname.startsWith('/api/')) {
    return new Response(null, {status:404});
  }
  const target = new URL('https://moduyuga-beta.onrender.com');
  target.pathname = incoming.pathname;
  target.search = incoming.search;
  const headers = new Headers();
  for (const name of ['accept','content-type','authorization','origin','user-agent',
    'access-control-request-method','access-control-request-headers','x-moduyuga-client',
    'range','if-none-match','if-modified-since']) {
    if (request.headers.has(name)) headers.set(name,request.headers.get(name));
  }
  try {
    return await send(target, {method:request.method, headers, body:request.body,
      redirect:'manual', cache:'no-store'});
  } catch {
    return Response.json({detail:'서버 응답을 받지 못했습니다.'},{status:503,
      headers:{'Cache-Control':'no-store'}});
  }
}

export default { fetch: request => routeRecoveryApi(request) };
