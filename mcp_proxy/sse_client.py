import asyncio
from pydantic import AnyUrl
from typing import Optional

from mcp import ClientSession
from mcp.client.sse import sse_client

async def run(url):
    """Run an interactive chat loop"""
    async with (
            sse_client(url=url) as streams,
    ClientSession(*streams) as session,
    ):
        await session.initialize()
        while True:
            cmd = input('>>> ')
            if cmd == 'q':
                return
            if cmd == '':
                continue
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
                    result = await session.call_tool(cmd_list[1], arguments=eval(cmd_list[2]))
                    print(result)
            except Exception as e:
                print("error: ", e)


if __name__ == "__main__":
    asyncio.run(run("http://127.0.0.1:8082/sse"))
