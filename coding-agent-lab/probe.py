import asyncio
import os
import sys

from agents import Agent, Runner, function_tool

MODEL = "gpt-5.4-mini"


@function_tool
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    with open(path, "r") as f:
        return f.read()


async def main():
    agent = Agent(
        name="Probe",
        instructions="You are a coding assistant. Read the file when asked.",
        model=MODEL,
        tools=[read_file],
    )
    result = await Runner.run(agent, "Read probe_target.py and tell me what it does in one line.")
    print("FINAL:", result.final_output)
    print("--- ITEMS ---")
    for item in result.new_items:
        print("TYPE:", item.type, "| CLASS:", type(item).__name__)
        raw = getattr(item, "raw_item", None)
        print("  raw class:", type(raw).__name__)
        for attr in ("name", "arguments", "call_id", "output", "content", "text", "type", "role"):
            if hasattr(raw, attr):
                val = getattr(raw, attr)
                print(f"  raw.{attr} = {str(val)[:300]}")
        for attr in ("name", "arguments", "output", "action"):
            if hasattr(item, attr):
                val = getattr(item, attr)
                print(f"  item.{attr} = {str(val)[:300]}")


if __name__ == "__main__":
    with open("probe_target.py", "w") as f:
        f.write("def square(n):\n    return n * n\n")
    asyncio.run(main())
