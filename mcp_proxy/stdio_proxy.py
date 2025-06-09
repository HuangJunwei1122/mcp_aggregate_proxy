from mcp import ClientSession
from mcp.client.stdio import stdio_client
from typing import Optional


class STDIOProxy:
    session: Optional[ClientSession]

    async def connect(self, server_params, stack):
        stdio_streams = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(*stdio_streams))
        await session.initialize()
        self.session = session
        return session

