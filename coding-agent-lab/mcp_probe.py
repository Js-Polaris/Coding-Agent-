import asyncio
import os
import sys

from agents import Agent, Runner
from agents.mcp import MCPServerStdio

MODEL = "gpt-5.4-mini"
NPX = "npx.cmd" if os.name == "nt" else "npx"


async def main():
    params = {"command": NPX, "args": ["-y", "@upstash/context7-mcp"]}
    async with MCPServerStdio(params=params, client_session_timeout_seconds=120) as server:
        listed = await server.list_tools()
        print("MCP TOOLS:", [t.name for t in listed])
        agent = Agent(
            name="Docs",
            instructions="Use Context7 to look up library documentation before answering.",
            model=MODEL,
            mcp_servers=[server],
        )
        result = await Runner.run(
            agent,
            "Use Context7 to find current FastAPI documentation about dependencies and summarise it in three bullets.",
        )
        print("ANSWER:\n", result.final_output)
        print("ITEM TYPES:", [i.type for i in result.new_items])
        for i in result.new_items:
            if i.type == "tool_call_item":
                print("CALL:", i.raw_item.name, getattr(i.raw_item, "arguments", "")[:200])


asyncio.run(main())
