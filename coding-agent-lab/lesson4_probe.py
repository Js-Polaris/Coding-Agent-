import asyncio
import os
import subprocess
import sys

from agents import Agent, Runner, function_tool

MODEL = "gpt-5.4-mini"
os.environ["PATH"] = os.path.dirname(sys.executable) + os.pathsep + os.environ["PATH"]


@function_tool
def run_command(command: str) -> str:
    """Run a shell command and return its output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    output = result.stdout
    if result.stderr:
        output += f"\nSTDERR:\n{result.stderr}"
    if result.returncode != 0:
        output += f"\n(exit code: {result.returncode})"
    return output[:10000] if output.strip() else "(no output)"


async def main():
    agent = Agent(
        name="Runner",
        instructions="You are a coding assistant. Use run_command to inspect the environment.",
        model=MODEL,
        tools=[run_command],
    )
    r = await Runner.run(agent, "What is the current git branch and the Python version?")
    print("ANSWER:\n", r.final_output)
    for i in r.new_items:
        if i.type == "tool_call_item":
            print("CALL:", i.raw_item.arguments)
        if i.type == "tool_call_output_item":
            print("OUT:", str(i.output)[:400])


asyncio.run(main())
