"""Reusable agent core: five primitives + B2 safety + B3 read_lines + B4 tracer + Part E search."""
from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import subprocess
import sys

from agents import Agent, function_tool

MODEL = "gpt-5.4-mini"

# ---------------------------------------------------------------- five primitives

MAX_CHARS = 10_000


@function_tool
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > MAX_CHARS:
            content = content[:MAX_CHARS] + "\n... (truncated)"
        return content
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except IsADirectoryError:
        return f"Error: {path} is a directory, not a file. Use list_files."
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
def edit_file(path: str, old_str: str, new_str: str) -> str:
    """Edit a file by replacing old_str with new_str.

    If old_str is empty the file is created, or appended to when it already exists.
    Otherwise old_str must appear exactly once, so edits are never ambiguous.
    """
    try:
        if old_str == "":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            mode = "a" if os.path.exists(path) else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(new_str)
            return f"{'Appended to' if mode == 'a' else 'Created'} {path}"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        count = content.count(old_str)
        if count == 0:
            return f"Error: old_str not found in {path}"
        if count > 1:
            return f"Error: old_str found {count} times in {path} (expected exactly 1)"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content.replace(old_str, new_str, 1))
        return f"Edited {path}"
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error editing file: {e}"


# ---------------------------------------------------------------- B2 safe runner

BLOCKED_PATTERNS = [
    "rm -rf",
    "rm -fr",
    "sudo",
    "shutdown",
    "mkfs",
    "format ",
    "del /f",
    "del /s",
    "rd /s",
    "rmdir /s",
    ":(){",
    "curl | sh",
    "curl|sh",
    "wget | sh",
    "wget|sh",
    "| sh",
    "| bash",
]

ALLOWED_PREFIXES = (
    "python",
    "python3",
    "py ",
    "pytest",
    "ls",
    "dir",
    "cat",
    "type ",
    "git status",
    "git diff",
    "git log",
)


def _blocked(command: str) -> str | None:
    low = " ".join(command.lower().split())
    for pattern in BLOCKED_PATTERNS:
        if pattern in low:
            return pattern
    return None


def _allowed(command: str) -> bool:
    low = command.strip().lower()
    return any(low == p.strip() or low.startswith(p) for p in ALLOWED_PREFIXES)


def _run_command(command: str) -> str:
    """Implement the safety policy, then run the command if it is permitted."""
    pattern = _blocked(command)
    if pattern:
        return (
            f"REFUSED: command contains blocked pattern {pattern!r}. "
            "It was not run. Use a safe alternative."
        )
    if not _allowed(command):
        try:
            answer = input(f"Allow this command? [y/N] {command}\n> ")
        except Exception:
            return (
                "REFUSED: this command needs interactive confirmation, but no "
                "operator is available in this non-interactive run. It was not run. "
                "Use an allowlisted command (python, pytest, ls, cat, git status, git diff)."
            )
        if answer.strip().lower() != "y":
            return f"REFUSED: the operator declined this command: {command!r}. It was not run."
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\n(exit code: {result.returncode})"
        if len(output) > MAX_CHARS:
            output = output[:MAX_CHARS] + "\n... (truncated)"
        return output if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds"
    except Exception as e:
        return f"Error running command: {e}"


@function_tool
def run_command(command: str) -> str:
    """Run a shell command. Dangerous commands are blocked, and commands outside the
    allowlist require the operator's confirmation."""
    return _run_command(command)


# ---------------------------------------------------------------- B3 read_lines


def _read_lines(path: str, start: int, end: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except IsADirectoryError:
        return f"Error: {path} is a directory, not a file."
    except Exception as e:
        return f"Error reading file: {e}"

    if start < 1:
        return "Error: start must be 1 or greater (line numbers are 1-based)."
    if end < start:
        return f"Error: start ({start}) is greater than end ({end})."
    if start > len(lines):
        return (
            f"Error: start line {start} is past the end of the file, "
            f"which has {len(lines)} lines."
        )
    last = min(end, len(lines))
    body = "".join(f"{n:>4} | {lines[n - 1]}" for n in range(start, last + 1))
    if not body.endswith("\n"):
        body += "\n"
    note = "" if end <= len(lines) else f"(end clipped to {last}; file has {len(lines)} lines)\n"
    return note + body


@function_tool
def read_lines(path: str, start: int, end: int) -> str:
    """Return only lines start..end (1-based, inclusive), each prefixed with its line number."""
    return _read_lines(path, start, end)


# ---------------------------------------------------------------- Part E search

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".ipynb_checkpoints",
}

MAX_MATCHES = 50


def _search_code(pattern: str, path: str = ".", file_type: str = "") -> str:
    """Pure-Python grep: regex search, skip noise directories, stop at 50 matches."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regular expression: {e}"
    suffix = ""
    if file_type:
        suffix = "." + file_type.lstrip(".")
    matches: list[str] = []
    try:
        for root, dirs, files in os.walk(path):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for name in sorted(files):
                if suffix and not name.endswith(suffix):
                    continue
                full = os.path.join(root, name)
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        for number, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append(f"{full}:{number}:{line.rstrip()}")
                                if len(matches) >= MAX_MATCHES:
                                    return (
                                        "\n".join(matches)
                                        + "\n... (truncated at 50 matches)"
                                    )
                except (OSError, UnicodeError):
                    continue
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    return "\n".join(matches) if matches else "No matches found"


@function_tool
def search_code(pattern: str, path: str = ".", file_type: str = "") -> str:
    """Search for a regex pattern in code files and return file:line:text matches.
    Skips .git, __pycache__, node_modules, .venv, venv and .ipynb_checkpoints.
    Optionally filter by file type (e.g. py)."""
    return _search_code(pattern, path, file_type)


# ---------------------------------------------------------------- B4 tracer


def _message_text(item) -> str:
    parts = []
    for block in getattr(item.raw_item, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) or "(no text)"


def show_trace(result) -> None:
    """Print every tool call, its arguments, the first 200 chars of its result, then the answer."""
    for step, item in enumerate(result.new_items, 1):
        if item.type == "tool_call_item":
            raw = item.raw_item
            print(f"[{step}] TOOL CALL   {raw.name}")
            print(f"      arguments:  {raw.arguments}")
        elif item.type == "tool_call_output_item":
            output = str(getattr(item, "output", item.raw_item))
            preview = output[:200] + ("..." if len(output) > 200 else "")
            print(f"[{step}] TOOL RESULT {preview!r}")
        elif item.type == "message_output_item":
            print(f"[{step}] ASSISTANT   {_message_text(item)}")
        else:
            print(f"[{step}] {item.type}")
    print("\nFINAL ANSWER\n" + "-" * 60)
    print(result.final_output)


# ---------------------------------------------------------------- agent factory

INSTRUCTIONS = """You are a careful coding assistant working in a Windows folder.

Work in this order:
1. Explore: list files and read the relevant source before changing anything.
2. Understand: run the code or tests to see the real failure.
3. Fix: make the smallest correct edit with edit_file. Match old_str exactly and
   include enough surrounding lines to make it unique.
4. Verify: re-run the tests after every change and keep going until they pass.

Rules:
- Run commands from the project root. Do NOT use cd.
- The virtual environment is on PATH, so use `python` (not python3).
- Use commands that start with python, pytest, ls, cat, git status or git diff.
- Never modify or delete test files. Fix the source, not the tests.
- If a tool refuses a command, read the refusal and choose a safe alternative.
- Report exactly what you changed and the final test output. Do not claim a test
  passed unless you ran it in this session.
"""


def make_agent(tools) -> Agent:
    return Agent(
        name="Coding Assistant",
        instructions=INSTRUCTIONS,
        model=MODEL,
        tools=tools,
    )


def test_hash(path: str = "assignment_starter/test_inventory.py") -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


ALL_TOOLS = [read_file, list_files, run_command, edit_file, search_code, read_lines]
