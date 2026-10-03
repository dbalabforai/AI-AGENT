import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = Path(__file__).with_name("mcp_server.py")


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.list_tools()

            print("MCP Server: local-files")
            print(f"Available tools ({len(result.tools)}):")

            for tool in result.tools:
                print(f"  • {tool.name} — {tool.description}")


if __name__ == "__main__":
    asyncio.run(main())