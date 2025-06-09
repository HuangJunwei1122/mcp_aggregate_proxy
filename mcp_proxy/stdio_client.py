import sys

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from typing import Optional

# Create server parameters for stdio connection
server_params = StdioServerParameters(
    command="python3",  # Executable
    args=["main.py"],  # Optional command line arguments
    env=None,  # Optional environment variables
)


# Optional: create a sampling callback
async def handle_sampling_message(
        message: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text="Hello, world! from model",
        ),
        model="gpt-3.5-turbo",
        stopReason="endTurn",
    )


async def run():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(
                read, write, sampling_callback=handle_sampling_message
        ) as session:
            print(f'connect to server server_params={server_params}')
            await session.initialize()

            resources: types.ListResourceTemplatesResult = await session.list_resource_templates()
            print(resources)
            prompts = await session.list_prompts()
            print(prompts)
            tools = await session.list_tools()
            print(tools)

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
                        print("exeute list_resources")
                        resources = await session.list_resource_templates()
                        print(resources)
                    elif cmd_list[0] == 'list_tools':
                        tools = await session.list_tools()
                        print(tools)
                    elif cmd_list[0] == 'read_resource':
                        content, mime_type = await session.read_resource(cmd_list[1])
                        print(content, mime_type)
                    elif cmd_list[0] == 'call_tool':
                        result = await session.call_tool(cmd_list[1], eval(cmd_list[2]))
                        print(result)
                except Exception as e:
                    print("error: ", e)


if __name__ == "__main__":
    import asyncio

    asyncio.run(run())
