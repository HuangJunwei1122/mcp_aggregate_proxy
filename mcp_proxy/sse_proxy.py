from mcp import ClientSession, StdioServerParameters, types
from mcp.client.sse import sse_client
from typing import Optional


class SSEProxy:
    session: Optional[ClientSession]

    async def connect(self, url, stack):
        streams = await stack.enter_async_context(sse_client(url))
        session = await stack.enter_async_context(ClientSession(*streams))
        await session.initialize()
        self.session = session
        return session
