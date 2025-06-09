from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from typing import Optional


class StreamableHttpProxy:
    session: Optional[ClientSession]

    async def connect(self, url, stack):
        _read, _write, _ = await stack.enter_async_context(streamablehttp_client(url))
        session = await stack.enter_async_context(ClientSession(_read, _write))
        await session.initialize()
        self.session = session
        return session
