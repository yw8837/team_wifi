"""Bound request buffering before JSON parsing (including chunked requests)."""
from starlette.responses import JSONResponse
from . import config


class BodyLimitMiddleware:
    def __init__(self, app, limit=65536):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return await self.app(scope, receive, send)
        limit = self.limit
        if scope['method'] == 'POST' and scope.get('path') == '/api/attachments' and not config.PUBLIC_RELEASE:
            limit = 20*1024*1024 + 65536
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body)+len(chunk) > limit:
                return await JSONResponse({'detail': '요청이 너무 큽니다.'}, status_code=413)(scope, receive, send)
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        consumed = False

        async def replay():
            nonlocal consumed
            if not consumed:
                consumed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)
