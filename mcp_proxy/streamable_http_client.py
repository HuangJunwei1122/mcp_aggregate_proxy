import asyncio
import json
import os
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import AnyUrl

load_dotenv()  # load environment variables from .env


class MCPClient:
    def __init__(self):
        # Initialize session and client objects
        self.session: Optional[ClientSession] = None


    async def run(self, server_url: str):
        """Connect to an MCP server running with streamablehttp transport"""
        # Store the context managers so they stay alive
        async with (
                streamablehttp_client(url=server_url) as (read, write, _),
        ClientSession(read, write) as session,
        ):
            await session.initialize()
            while True:
                cmd = input('>>> ')
                if cmd == 'q':
                    return
                try:
                    cmd_list = cmd.split()
                    if cmd_list[0] == 'list_prompts':
                        prompts = await session.list_prompts()
                        print(prompts)
                    elif cmd_list[0] == 'get_prompt':
                        prompt = await session.get_prompt(
                            cmd_list[1], arguments=eval(cmd_list[2])
                        )
                        print(prompt)
                    elif cmd_list[0] == 'list_resource_templates':
                        resources = await session.list_resource_templates()
                        print(resources)
                    elif cmd_list[0] == 'list_tools':
                        resources = await session.list_tools()
                        print(resources)
                    elif cmd_list[0] == 'read_resource':
                        content, mime_type = await session.read_resource(AnyUrl(cmd_list[1]))
                        print(content, mime_type)
                    elif cmd_list[0] == 'call_tool':
                        result = await session.call_tool(cmd_list[1], eval(cmd_list[2]))
                        print(result)
                except Exception as e:
                    print("error: ", e)


async def main():
    client = MCPClient()
    try:
        await client.run(server_url="http://127.0.0.1:8082/mcp")
    finally:
        print(f"exit")


if __name__ == "__main__":
    asyncio.run(main())
