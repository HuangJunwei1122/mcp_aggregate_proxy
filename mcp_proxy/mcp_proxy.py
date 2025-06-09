import asyncio
import json
from datetime import timedelta
from typing import Any
import typing as t
import contextlib
from collections.abc import AsyncIterator

from mcp import StdioServerParameters
import mcp.types as types
from mcp.shared.session import ProgressFnT
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl
from starlette.requests import Request
from starlette.applications import Starlette
from starlette.types import Receive, Scope, Send
from starlette.routing import Mount, Route
from mcp.server import Server

import uvicorn

from stdio_proxy import STDIOProxy
from sse_proxy import SSEProxy
from streamable_http_proxy import StreamableHttpProxy

PROXY_NAME = "mpc-proxy-demo"


class MCPProxy:
    def __init__(self):
        self.server = {}
        self.conf = self.get_server_conf()

    @staticmethod
    def get_server_conf():
        with open('./mcp_server_conf.json') as f:
            return json.load(f)

    async def connect_mcp_server(self, stack):
        for server_conf in self.conf.get('mcp_server', []):
            transport = server_conf.get('transport', '')
            if transport == 'stdio':
                proxy = STDIOProxy()
                await proxy.connect(StdioServerParameters(
                    command=server_conf['command'],  # Executable
                    args=server_conf['args'],  # Optional command line arguments
                    env=None,  # Optional environment variables
                ), stack)
                self.server[server_conf['name']] = {
                    'transport': 'stdio',
                    'proxy': proxy
                }
            elif transport == 'sse':
                proxy = SSEProxy()
                await proxy.connect(server_conf['url'], stack)
                self.server[server_conf['name']] = {
                    'transport': 'sse',
                    'proxy': proxy
                }
            elif transport == 'streamable-http':
                proxy = StreamableHttpProxy()
                await proxy.connect(server_conf['url'], stack)
                self.server[server_conf['name']] = {
                    'transport': 'streamable-http',
                    'proxy': proxy
                }

    async def run(self, transport):
        async with contextlib.AsyncExitStack() as stack:
            try:
                await self.connect_mcp_server(stack)
                print(f'========connect_mcp_server done========')
                print(f'server({len(self.server)}): {self.server}')
                server = await self.create_proxy_server()
                print(f'========create_proxy_server done========')
                if transport == 'stdio':
                    print(f'========start stdio========')
                    await self.run_stdio_proxy(server)
                elif transport == 'sse' or transport == 'streamable-http':
                    print(f'========start sse or streamable-http========')
                    await self.run_sse_streamable_http_proxy(server, True)
            except Exception as e:
                print(f"proxy run exit with error={e}")

    async def create_proxy_server(self) -> Server[object]:  # noqa: C901, PLR0915
        """Create a server instance from a remote app."""
        capabilities = types.ServerCapabilities()
        for name, server in self.server.items():
            if server['proxy'].session:
                response = await server['proxy'].session.initialize()
                cap = response.capabilities
                capabilities.prompts = capabilities.prompts or cap.prompts
                capabilities.resources = capabilities.resources or cap.resources
                capabilities.tools = capabilities.tools or cap.tools

        app: Server[object] = Server(name=PROXY_NAME)
        print(f'create_proxy_server capabilities={capabilities}')

        async def _list_prompts(_: t.Any) -> types.ServerResult:  # noqa: ANN401
            print(f'in create_proxy_server _list_prompts')
            result = await self.list_prompts()
            print(f'in create_proxy_server _list_prompts, result={result}')
            return types.ServerResult(result)

        app.request_handlers[types.ListPromptsRequest] = _list_prompts

        async def _get_prompt(req: types.GetPromptRequest) -> types.ServerResult:
            print(f'in create_proxy_server _get_prompt')
            result = await self.get_prompt(req.params.name, req.params.arguments)
            print(f'in create_proxy_server _get_prompt, result={result}')
            return types.ServerResult(result)

        app.request_handlers[types.GetPromptRequest] = _get_prompt

        async def _list_resources(_: t.Any) -> types.ServerResult:  # noqa: ANN401
            print("in handle _list_resources")
            result = await self.list_resources()
            print(f"in handle _list_resources, result={result}")
            return types.ServerResult(result)

        app.request_handlers[types.ListResourcesRequest] = _list_resources

        async def _list_resource_templates(_: t.Any) -> types.ServerResult:  # noqa: ANN401
            print(f'in _list_resource_templates')
            result = await self.list_resource_templates()
            print(f'in _list_resource_templates, result={result}')
            return types.ServerResult(result)

        app.request_handlers[types.ListResourceTemplatesRequest] = _list_resource_templates

        async def _read_resource(req: types.ReadResourceRequest) -> types.ServerResult:
            result = await self.read_resource(req.params.uri)
            return types.ServerResult(result)

        app.request_handlers[types.ReadResourceRequest] = _read_resource

        async def _list_tools(_: t.Any) -> types.ServerResult:  # noqa: ANN401
            tools = await self.list_tools()
            return types.ServerResult(tools)

        app.request_handlers[types.ListToolsRequest] = _list_tools

        async def _call_tool(req: types.CallToolRequest) -> types.ServerResult:
            try:
                result = await self.call_tool(
                    req.params.name,
                    (req.params.arguments or {}),
                )
                return types.ServerResult(result)
            except Exception as e:  # noqa: BLE001
                return types.ServerResult(
                    types.CallToolResult(
                        content=[types.TextContent(type="text", text=str(e))],
                        isError=True,
                    ),
                )

        app.request_handlers[types.CallToolRequest] = _call_tool

        return app

    async def run_stdio_proxy(self, server: Server):
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
        await self.close()

    async def run_sse_streamable_http_proxy(self, mcp_server: Server, debug: bool):
        http_session_manager = StreamableHTTPSessionManager(
            app=mcp_server,
            event_store=None,
            json_response=True,
            stateless=False,
        )
        sse_transport = SseServerTransport("/messages/")

        async def handle_streamable_http_instance(scope: Scope, receive: Receive, send: Send) -> None:
            print(f'in handle_streamable_http_instance, scope={scope}, receive={receive}, send={send}')
            await http_session_manager.handle_request(scope, receive, send)

        async def handle_sse_instance(request: Request) -> None:
            print(f'in handle_sse_instance, request={request}')
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

        starlette_app = Starlette(
            debug=debug,
            routes=[
                Mount("/mcp", app=handle_streamable_http_instance),
                Route("/sse", endpoint=handle_sse_instance),
                Mount("/messages/", app=sse_transport.handle_post_message),
            ],
            lifespan=lifespan
        )

        config = uvicorn.Config(
            starlette_app,
            port=8082,
        )

        http_server = uvicorn.Server(config)
        await http_server.serve()

    @staticmethod
    def gen_server_key(server_name, v):
        return f'{server_name}/{v}'

    @staticmethod
    def parse_server_key(name):
        return name.split('/', 1)

    async def list_prompts(self, cursor: str | None = None) -> types.ListPromptsResult:
        all_prompts = []
        for name, server in self.server.items():
            if server['proxy'].session:
                prompts_res = await server['proxy'].session.list_prompts()
                prompts = prompts_res.prompts
                for prompt in prompts:
                    prompt.name = self.gen_server_key(name, prompt.name)
                all_prompts.extend(prompts)
        res = types.ListPromptsResult(prompts=all_prompts)
        res.prompts = all_prompts
        return res

    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
        parsed_key = self.parse_server_key(name)
        if len(parsed_key) != 2 or parsed_key[0] not in self.server or not self.server[parsed_key[0]]['proxy']:
            print(f'in self get_prompt invalid')
        server_name, name = parsed_key
        server = self.server[server_name]['proxy'].session
        return await server.get_prompt(name, arguments=arguments)

    async def list_resources(self, cursor: str | None = None) -> types.ListResourcesResult:
        all_resources = []
        for name, server in self.server.items():
            if server['proxy']:
                resources_res = await server['proxy'].session.list_resources()
                resources = resources_res.resources
                for resource in resources:
                    resource.uri = self.gen_server_key(name, resource.uri)
                all_resources.extend(resources)
        res = types.ListResourcesResult(resources=all_resources)
        return res

    async def list_resource_templates(self, cursor: str | None = None) -> types.ListResourceTemplatesResult:
        print(f'in self.list_resource_templates, self.server={self.server}')
        all_resourceTemplates = []
        for name, server in self.server.items():
            if server['proxy']:
                resources_res = await server['proxy'].session.list_resource_templates()
                resources = resources_res.resourceTemplates
                for resource in resources:
                    resource.uriTemplate = self.gen_server_key(name, resource.uriTemplate)
                all_resourceTemplates.extend(resources)
                print(f'list_resource_templates, all_resourceTemplates={all_resourceTemplates}')
        res = types.ListResourceTemplatesResult(resourceTemplates=all_resourceTemplates)
        return res

    async def read_resource(self, uri: AnyUrl) -> types.ReadResourceResult:
        parsed_key = self.parse_server_key(uri.scheme)
        if len(parsed_key) != 2 or parsed_key[0] not in self.server or not self.server[parsed_key[0]]['proxy']:
            return types.ReadResourceResult()
        server_name, uri = parsed_key
        server = self.server[server_name]['proxy'].session
        return await server.read_resource(AnyUrl(uri))

    async def list_tools(self, cursor: str | None = None) -> types.ListToolsResult:
        all_tools = []
        for name, server in self.server.items():
            if server['proxy']:
                tools_res = await server['proxy'].session.list_tools()
                tools = tools_res.tools
                for tool in tools:
                    tool.name = self.gen_server_key(name, tool.name)
                all_tools.extend(tools)
        res = types.ListToolsResult(tools=all_tools)
        return res

    async def call_tool(
            self,
            name: str,
            arguments: dict[str, Any] | None = None,
            read_timeout_seconds: timedelta | None = None,
            progress_callback: ProgressFnT | None = None,
    ) -> types.CallToolResult:
        parsed_key = self.parse_server_key(name)
        if len(parsed_key) != 2 or parsed_key[0] not in self.server or not self.server[parsed_key[0]]['proxy']:
            return types.CallToolResult()
        server_name, name = parsed_key
        server = self.server[server_name]['proxy'].session
        return await server.call_tool(name, arguments=arguments)
