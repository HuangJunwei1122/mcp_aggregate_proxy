import asyncio
import sys

from mcp_proxy import MCPProxy


if __name__ == '__main__':
    print(f'sys.argv={sys.argv}')
    if len(sys.argv) < 2:
        transport = 'stdio'
    else:
        transport = sys.argv[1]
    print(f'transport={transport}')
    proxy = MCPProxy()
    asyncio.run(proxy.run(transport))
