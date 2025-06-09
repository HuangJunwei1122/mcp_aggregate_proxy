import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.types import Receive, Scope, Send
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn

# Initialize FastMCP server for Weather tools (StreamableHttp)
mcp = FastMCP("demo_streamable")

# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


# Add a prompt
@mcp.prompt()
def translation_ja(txt: str) -> str:
    """Translating to Japanese"""
    return f"Please translate this sentence into Japanese: {txt}"


def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with StreamableHttp."""
    http_session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=True,
        stateless=False,
    )
    sse_transport = SseServerTransport("/messages/")

    async def handle_streamable_http_instance(scope: Scope, receive: Receive, send: Send) -> None:
        await http_session_manager.handle_request(scope, receive, send)

    async def handle_sse_instance(request: Request) -> None:
        async with sse_transport.connect_sse(
            request.scope,
            request.receive,
            request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        """Context manager for managing session manager lifecycle."""
        async with http_session_manager.run():
            print("Application started with StreamableHTTP session manager!")
            try:
                yield
            finally:
                print("Application shutting down...")

    return Starlette(
        debug=debug,
        routes=[
            Mount("/mcp", app=handle_streamable_http_instance),
            Route("/sse", endpoint=handle_sse_instance),
            Mount("/messages/", app=sse_transport.handle_post_message),
        ],
        lifespan=lifespan
    )


def main():
    mcp_server = mcp._mcp_server
    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, port=8081)


if __name__ == "__main__":
    main()
