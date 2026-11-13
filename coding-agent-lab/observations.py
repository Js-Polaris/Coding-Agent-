"""Collect real observations for the Part A 'check yourself' answers."""
import asyncio
import os
import subprocess
import sys
import io

from agents import Agent, Runner, function_tool

MODEL = "gpt-5.4-mini"
OUT = []


def log(*args):
    line = " ".join(str(a) for a in args)
    OUT.append(line)
    print(line)


@function_tool
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    try:
        with open(path, "r") as f:
            content = f.read()
        if len(content) > 10000:
            content = content[:10000] + "\n... (truncated)"
        return content
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


@function_tool
def list_files(path: str = ".") -> str:
    """List all files and directories at the given path. Directories end with /."""
    try:
        entries = []
        for entry in sorted(os.listdir(path)):
            full = os.path.join(path, entry)
            entries.append(f"{entry}/" if os.path.isdir(full) else entry)
        return "\n".join(entries) if entries else "(empty directory)"
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    except Exception as e:
        return f"Error listing files: {e}"


@function_tool
def run_command(command: str) -> str:
    """Run a shell command and return its output."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n(exit code: {result.returncode})"
        return output[:10000] if output.strip() else "(no output)"
    except Exception as e:
        return f"Error running command: {e}"


@function_tool
def edit_file(path: str, old_str: str, new_str: str) -> str:
    """Edit a file by replacing old_str with new_str. If old_str is empty, creates the file (or appends if it exists)."""
    try:
        if old_str == "":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            mode = "a" if os.path.exists(path) else "w"
            with open(path, mode) as f:
                f.write(new_str)
            return f"{'Appended to' if mode == 'a' else 'Created'} {path}"
        with open(path, "r") as f:
            content = f.read()
        count = content.count(old_str)
        if count == 0:
            return f"Error: old_str not found in {path}"
        if count > 1:
            return f"Error: old_str found {count} times in {path} (expected exactly 1)"
        with open(path, "w") as f:
            f.write(content.replace(old_str, new_str, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error editing file: {e}"


def calls(result):
    out = []
    for item in result.new_items:
        if item.type == "tool_call_item":
            out.append(f"{item.raw_item.name}({item.raw_item.arguments})")
    return out


async def lesson1():
    agent = Agent(
        name="Tutor",
        instructions="You are a concise programming tutor.",
        model=MODEL,
    )
    r1 = await Runner.run(agent, "In one sentence, what are the SOLID principles?")
    log("L1 first answer:", r1.final_output)
    r2 = await Runner.run(agent, "What did I just ask you?")
    log("L1 stateless answer:", r2.final_output)

    bullets = Agent(
        name="Bullets",
        instructions="You are a programming tutor. Answer only in bullet points, nothing else.",
        model=MODEL,
    )
    r3 = await Runner.run(bullets, "Name three benefits of writing tests.")
    log("L1 bullet answer:", r3.final_output)


async def lesson2():
    agent = Agent(
        name="Reader",
        instructions="You are a coding assistant. Use the read_file tool.",
        model=MODEL,
        tools=[read_file],
    )
    r = await Runner.run(agent, "Read no_such_file.py and explain it.")
    log("L2 missing-file answer:", r.final_output)
    log("L2 item order:", [i.type for i in r.new_items])
    for i in r.new_items:
        if i.type == "tool_call_output_item":
            log("L2 tool output:", str(i.output))


async def lesson3():
    os.makedirs("obs_files", exist_ok=True)
    open("obs_files/alpha.py", "w").write("def alpha():\n    return 'a'\n")
    open("obs_files/beta.py", "w").write("def beta(n):\n    return n + 1\n")
    open("obs_files/notes.txt", "w").write("not python\n")
    agent = Agent(
        name="Explorer",
        instructions="You are a coding assistant. Explore before answering.",
        model=MODEL,
        tools=[list_files, read_file],
    )
    r = await Runner.run(agent, "Which Python files exist in obs_files and what does each one do?")
    log("L3 answer:", r.final_output)
    log("L3 calls:", calls(r))


async def lesson4():
    agent = Agent(
        name="Runner",
        instructions="You are a coding assistant. Use run_command to inspect the environment.",
        model=MODEL,
        tools=[run_command],
    )
    r = await Runner.run(agent, "What is the current git branch and the Python version?")
    log("L4 answer:", r.final_output)
    log("L4 calls:", calls(r))
    for i in r.new_items:
        if i.type == "tool_call_output_item":
            log("L4 tool output:", str(i.output)[:500])


async def lesson5():
    open("obs_rename.py", "w").write(
        "def summarise(values):\n"
        "    count = 0\n"
        "    for v in values:\n"
        "        count = count + v\n"
        "    return count\n"
    )
    agent = Agent(
        name="Editor",
        instructions=(
            "You are a coding assistant. Use edit_file to change code. "
            "Change exactly what is asked and nothing else."
        ),
        model=MODEL,
        tools=[read_file, edit_file],
    )
    r = await Runner.run(
        agent,
        "In obs_rename.py rename the variable 'count' to 'total'. Do not change anything else.",
    )
    log("L5 rename answer:", r.final_output)
    log("L5 calls:", calls(r))
    log("L5 file after:\n" + open("obs_rename.py").read())


async def main():
    for fn in (lesson1, lesson2, lesson3, lesson4, lesson5):
        log("\n===== " + fn.__name__ + " =====")
        await fn()
    with open("observations.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(OUT))


asyncio.run(main())
