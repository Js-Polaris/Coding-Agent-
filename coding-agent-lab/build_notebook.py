"""Build assignment_Kabunga_Akram_Joshua.ipynb."""
import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

cells = []


def md(text: str):
    cells.append(new_markdown_cell(text.strip("\n")))


def code(text: str):
    cells.append(new_code_cell(text.strip("\n")))


# ------------------------------------------------------------------ title
md(r"""
# Building, Hardening and Testing a Coding Agent

**Student:** Kabunga Akram Joshua  
**Course:** Prompt Engineering — Agentic Programming  
**Model:** `gpt-5.4-mini`  
**Date:** November 2026

This notebook is the submission for the assignment *Build, harden and test your own coding agent*.
It starts from the Lesson 6 agent (`code_search.ipynb`), explains how it works, adds four
improvements (B1–B4), uses the agent to repair `assignment_starter/inventory.py`, reflects on the
result, and includes the Part E bonus.

## How to run

1. Create a virtual environment and install the dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   pip install openai-agents jupyter pytest
   ```

2. Put `assignment_starter/` next to this notebook. It contains `inventory.py` (the buggy module),
   `inventory_buggy.py` (a pristine copy used to reset Part C), and `test_inventory.py`.

3. Export the key in the terminal before starting Jupyter (never paste it into a cell):

   ```bash
   set OPENAI_API_KEY=sk-...      # Windows
   export OPENAI_API_KEY=sk-...   # macOS / Linux
   ```

4. Run all cells top to bottom. Part C makes live API calls.

> The key is read from `OPENAI_API_KEY`; there is no key anywhere in this notebook.
""")

code(r"""
# Run once in a fresh environment (uncomment):
# %pip install openai-agents jupyter pytest

import hashlib
import os
import re
import shutil
import subprocess
import sys
from getpass import getpass

from agents import Agent, Runner, function_tool

MODEL = "gpt-5.4-mini"

# Make this kernel's virtual environment the `python` that tool calls see.
venv_scripts = os.path.dirname(sys.executable)
if venv_scripts not in os.environ.get("PATH", "").split(os.pathsep):
    os.environ["PATH"] = venv_scripts + os.pathsep + os.environ.get("PATH", "")

if not os.environ.get("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = getpass("Enter your OpenAI API key: ")

print("Working directory:", os.getcwd())
print("Python:", sys.version.split()[0])
print("Model:", MODEL)
print("API key present:", bool(os.environ.get("OPENAI_API_KEY")))
""")

# ------------------------------------------------------------------ Part A
md(r"""
## Part A — Explain it

### A1. Check-yourself questions (14 marks)

Each answer is 2–4 sentences and quotes the output I actually observed with `gpt-5.4-mini`,
except where the question is conceptual.

#### Lesson 1 — `basic_chat.ipynb`

**1. Ask "What did I just ask you?" in a new cell. What happens, and why?**

The agent has no memory between calls. `Runner.run` sends only the current input, so the second run
never sees the first question. It replied:

```text
You asked: "What did I just ask you?"
```

It simply echoed the new question instead of recalling the SOLID question — proof that every call is
stateless until we pass a history list (Part B1).

**2. Change `instructions` to make the agent answer only in bullet points. Does the output change?**

Yes. `instructions` is the system prompt, so it is the strongest steering signal for style. With
`instructions="... Answer only in bullet points, nothing else."` the same kind of question came back as:

```text
- Catches bugs early
- Makes code safer to change
- Documents expected behavior
```

#### Lesson 2 — `file_reader.ipynb`

**1. Ask the agent to read a file that does not exist. What does it say?**

The tool catches `FileNotFoundError` and returns an error string instead of raising, so the loop keeps
running and the model can recover. The tool returned `Error: File not found: no_such_file.py`, and the
agent answered:

```text
I couldn't read `no_such_file.py` because it doesn't exist at that path.

If you want, send the correct path or paste the file contents here, and I'll explain it.
```

**2. After a run, print `item.type` for `result.new_items`. Which types appear, and in what order?**

Observed order:

```text
['tool_call_item', 'tool_call_output_item', 'message_output_item']
```

That is the loop in miniature: the model asks for a tool, the SDK executes it and appends the result,
then the model writes the final message.

#### Lesson 3 — `file_explorer.ipynb`

**1. Put two or three small `.py` files in the folder and re-run. How many tool calls did the agent make?**

With `alpha.py`, `beta.py` and `notes.txt`, the agent made **4** calls without being told to chain them:

```text
list_files({"path": "obs_files"})
read_file({"path": "obs_files/alpha.py"})
read_file({"path": "obs_files/beta.py"})
read_file({"path": "obs_files/notes.txt"})
```

It discovered the directory, then read each candidate file before answering.

**2. What would go wrong if the docstring said nothing about directories ending in `/`?**

The model could not tell a directory from a file, because the tool returns bare names. It might call
`read_file("obs_files")`, get an `IsADirectoryError`, and waste turns — or it might claim a folder is an
empty file. The `/` suffix in the docstring/output is the only signal that distinguishes them.

#### Lesson 4 — `command_runner.ipynb`

**1. Run it in a folder that is not a git repository. How does the agent report the error?**

The tool returned stderr and the exit code, and the agent summarised it honestly:

```text
fatal: not a git repository (or any of the parent directories): .git
(exit code: 128)

Git branch: not in a git repository
```

A second call, `python3 --version`, hit the Windows Store alias and returned exit code `9009`; the agent
then said Python was unavailable. Python *was* installed in the venv — the lesson is that the agent
reports what the shell returns, not the truth about the machine.

**2. Name two commands you would never want an agent to run without asking you first.**

`rm -rf` on a real project folder (or `del /f /s` on Windows) and `shutdown`. I would add
`curl ... | sh` to that list, because it executes arbitrary remote code. All three are blocked in B2.

#### Lesson 5 — `file_editor.ipynb`

**1. Ask the agent to rename a variable that appears three times. Watch how it handles the exactly-once rule.**

It read the file once, then made one `edit_file` call whose `old_str` was the whole four-line block
containing all three occurrences, not three separate edits:

```text
read_file({"path": "obs_rename.py"})
edit_file({"path": "obs_rename.py",
           "old_str": "    count = 0\n    for v in values:\n        count = count + v\n    return count\n",
           "new_str": "    total = 0\n    for v in values:\n        total = total + v\n    return total\n"})
```

Because the block occurs once, the edit is unambiguous. An `old_str` of just `count` would have been
refused with “found 3 times (expected exactly 1)”, forcing the model to add context.

**2. What happens if the agent calls `edit_file` with an empty `old_str` on an existing file?**

It **appends** rather than overwrites: the code chooses mode `"a"` when the path exists. That is useful
for adding a block, but dangerous for a “rewrite this file” request — the old contents survive and the
result is a mix of both versions.

#### Lesson 6 — `code_search.ipynb`

**1. Why search with grep instead of reading every file with `read_file`?**

Search returns only the matching `file:line:text` rows, so the model's context stays small and relevant.
Reading every file would flood the context window, cost far more tokens, and still require the model to
scan for the pattern itself. Search is also the cheapest way to find *where* to read next.

**2. Why does the cell creating `hello.py` change the answer to the search question?**

`search_code` walks the live filesystem, not a snapshot. Once `hello.py` exists and contains `import os`,
the same query legally finds one more file. It also shows that an agent's answer depends on the order in
which it modifies and inspects the workspace.

#### Lesson 7 — `mcp_context7.ipynb`

**1. When would you write your own tool, and when would you look for an MCP server instead?**

Write your own tool for project-specific behaviour, private APIs, or a safety policy you must control
(such as the B2 allowlist). Reach for an MCP server when a maintained server already exposes a standard
capability — documentation, a database, a browser — so you get updates and interoperability without
maintaining the integration. Mixing both, as the lesson does, is normal.

**2. Ask about a library released or changed recently. Does Context7 give a better answer than Lesson 1's agent?**

Yes. The server exposed `resolve-library-id` and `query-docs`; the agent made two MCP calls and answered
from current FastAPI docs rather than its training data:

```text
- Use `Depends(...)` ... `Annotated[...]` is the preferred style ...
- Dependencies can be nested and can `yield` values for setup/teardown ...
- You can override dependencies in tests with `app.dependency_overrides[...]` ...
```

That specificity (yield-dependencies and overrides) is the difference between live documentation and a
plausible memory.
""")

md(r"""
### A2. One full trace of the Lesson 5 FizzBuzz run (6 marks)

The prompt was roughly: *“Write a FizzBuzz program in `hello_world.py`, run it, and count the files in the
folder.”* The numbered trace below follows the actual message flow between the user, the SDK, the LLM and
my Python functions.

1. **User → SDK.** Jupyter calls `await Runner.run(agent, prompt)`. The SDK builds a request containing the
   agent's `instructions`, the JSON schemas of all five tools, and the user message.
2. **LLM (turn 1).** The model decides it needs to write a file and returns a *tool call* instead of text:
   `edit_file(path="fizzbuzz.py", old_str="", new_str="for i in range(1, 16): ...")`. Note that it chose
   `fizzbuzz.py`, not the requested `hello_world.py` — the first sign that the plan is not followed exactly.
3. **SDK → Python.** The SDK looks up the registered tool, validates the arguments against the schema, and
   calls the real `edit_file` function.
4. **Python → SDK.** `old_str` is empty and the file is missing, so the function takes the *create* branch,
   writes the file, and returns the string `Created fizzbuzz.py`.
5. **SDK → LLM (turn 2).** The tool result is appended as a `tool_call_output_item` and the model is called
   again with the extended conversation.
6. **LLM (turn 2).** It asks to run the program: `run_command(command="python fizzbuzz.py")`.
7. **SDK → Python.** `run_command` executes `subprocess.run(..., shell=True, capture_output=True,
   timeout=30)` and returns stdout (`1, 2, Fizz, ... 15`), any stderr, and a non-zero exit code if present.
8. **SDK → LLM (turn 3).** The output is appended. The model now asks for `list_files(".")` to answer the
   “count the files” part.
9. **LLM (final).** With the directory listing in context it writes a normal `message_output_item`: the
   program works, here is the output, and there are *N* files.
10. **SDK → user.** `Runner.run` returns a `RunResult`; `result.final_output` is printed, and
    `result.new_items` contains the whole audit trail (`tool_call_item`, `tool_call_output_item`,
    `message_output_item`, …).

The important observation is step 10: the agent's summary said “done”, but the filename was wrong. The
trace, not the prose, is the source of truth — which is why Part B4 adds `show_trace`.
""")

# ------------------------------------------------------------------ Part B
md(r"""
## Part B — Extend the agent

### The five core primitives

The functions below are copied from `code_search.ipynb`. One deliberate change: `search_code` is the
pure-Python rewrite from Part E, because this machine is Windows and has no `grep`. It keeps the same
`file:line:text` output, the same skip-folders and the same 50-match limit.
""")

code(r'''
import re

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


SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".ipynb_checkpoints"}
MAX_MATCHES = 50


def _search_code(pattern: str, path: str = ".", file_type: str = "") -> str:
    """Pure-Python grep: regex search, skip noise directories, stop at 50 matches."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regular expression: {e}"
    suffix = "." + file_type.lstrip(".") if file_type else ""
    matches = []
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
                                    return "\n".join(matches) + "\n... (truncated at 50 matches)"
                except (OSError, UnicodeError):
                    continue
    except FileNotFoundError:
        return f"Error: Directory not found: {path}"
    return "\n".join(matches) if matches else "No matches found"


@function_tool
def search_code(pattern: str, path: str = ".", file_type: str = "") -> str:
    """Search for a regex pattern in code files and return file:line:text matches.
    Skips .git, __pycache__, node_modules, .venv, venv and .ipynb_checkpoints.
    Optionally filter by file type (e.g. py). Stops at 50 matches."""
    return _search_code(pattern, path, file_type)


print("Five primitives ready:", [t.name for t in (read_file, list_files, search_code, edit_file)])
''')

# ---------------- B1
md(r"""
### B1. Conversation memory (10 marks)

`Runner.run` is stateless, so `chat()` keeps a list. After each turn I replace the list with
`result.to_input_list()`, which contains the user message, the tool calls, the tool outputs and the
assistant reply. The next request is therefore `history + [new user message]`.

The interactive loop is `chat()` below. The cell also runs a **scripted** proof, because a notebook that
calls `input()` cannot run unattended: turn 1 asks the agent to read `memory_demo.py`, and turn 2 asks a
follow-up about “that file” without naming it again.
""")

code(r'''
with open("memory_demo.py", "w", encoding="utf-8") as f:
    f.write(
        "def double(n):\n"
        "    \"\"\"Return twice n.\"\"\"\n"
        "    return n * 2\n\n\n"
        "def greet(name):\n"
        "    return f\"Hello, {name}!\"\n"
    )

memory_agent = Agent(
    name="Memory Assistant",
    instructions="You are a coding assistant. Read files when asked and remember the conversation.",
    model=MODEL,
    tools=[read_file, list_files],
)


async def chat(agent):
    """Interactive chat loop: history survives between turns, exit stops."""
    history = []
    while True:
        try:
            user = input("you> ")
        except (EOFError, KeyboardInterrupt):
            break
        if user.strip().lower() in {"exit", "quit"}:
            break
        result = await Runner.run(agent, history + [{"role": "user", "content": user}])
        print("agent>", result.final_output)
        history = result.to_input_list()


async def scripted_demo(agent, turns):
    """Same logic as chat(), with the turns supplied in advance for reproducibility."""
    history = []
    for text in turns:
        print("you>", text)
        result = await Runner.run(agent, history + [{"role": "user", "content": text}])
        calls = [
            f"{item.raw_item.name}({item.raw_item.arguments})"
            for item in result.new_items
            if item.type == "tool_call_item"
        ]
        print("  tool calls:", calls or "(none)")
        print("agent>", result.final_output)
        history = result.to_input_list()
    print("\nHistory entry kinds:", [m.get("role") or m.get("type") for m in history])
    return history


await scripted_demo(
    memory_agent,
    [
        "Read memory_demo.py and tell me what it does.",
        "What does the function in that file return when you pass 21?",
    ],
)

print("\nTip: run `await chat(memory_agent)` in Jupyter to type turns; type 'exit' to stop.")
''')

md(r"""
**Proof.** Turn 1 made a `read_file` tool call. Turn 2 made **no** tool call and still answered `42`,
because the file contents were already in the conversation history. Without `history = result.to_input_list()`
the second turn would have had to guess or re-read the file. `chat()` is the same logic with `input()`
driving the turns, and `exit`/`quit` (or Ctrl-C) stops it.
""")

# ---------------- B2
md(r"""
### B2. A safer `run_command` (10 marks)

The policy is applied in a fixed order:

1. **Blocklist first** — dangerous fragments are refused even if the command starts with an allowlisted
   program (`git status; rm -rf /` is still refused).
2. **Allowlist second** — `python`, `pytest`, `ls`, `cat`, `git status` and `git diff` run immediately.
3. **Confirmation last** — anything else prints `Allow this command? [y/N]` and runs only on `y`.
4. **Every refusal returns a message** the LLM can read, including which rule fired and what to do instead.

The demos below show one blocked, one allowed and one confirmed command. The confirmed demo temporarily
replaces `input()` with a function that prints the prompt and types `y`, so the notebook stays
reproducible; in a terminal the same prompt waits for a real keystroke.
""")

code(r'''
import builtins

BLOCKED_PATTERNS = [
    "rm -rf", "rm -fr", "sudo", "shutdown", "mkfs", "format ",
    "del /f", "del /s", "rd /s", "rmdir /s", ":(){",
    "curl | sh", "curl|sh", "wget | sh", "wget|sh", "| sh", "| bash",
]

ALLOWED_PREFIXES = (
    "python", "python3", "py ", "pytest", "ls", "dir", "cat", "type ",
    "git status", "git diff", "git log",
)


def _blocked(command: str):
    low = " ".join(command.lower().split())
    for pattern in BLOCKED_PATTERNS:
        if pattern in low:
            return pattern
    return None


def _allowed(command: str) -> bool:
    low = command.strip().lower()
    return any(low == p.strip() or low.startswith(p) for p in ALLOWED_PREFIXES)


def _run_command(command: str) -> str:
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
                "REFUSED: this command needs interactive confirmation, but no operator is "
                "available in this non-interactive run. It was not run. Use an allowlisted "
                "command (python, pytest, ls, cat, git status, git diff)."
            )
        if answer.strip().lower() != "y":
            return f"REFUSED: the operator declined this command: {command!r}. It was not run."
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
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
    """Run a shell command. Dangerous commands are blocked; commands outside the allowlist
    require the operator's confirmation."""
    return _run_command(command)


print("1. BLOCKED")
print(_run_command("sudo rm -rf /"))
print()
print("2. ALLOWED (runs straight away)")
print(_run_command("python --version"))
print()
print("3. NEEDS CONFIRMATION (simulated operator types y)")
real_input = builtins.input


def fake_input(prompt=""):
    print(prompt, end="")
    print("y")
    return "y"


builtins.input = fake_input
try:
    print(_run_command("echo hello from the agent"))
finally:
    builtins.input = real_input
''')

md(r"""
**One way an LLM could still get round these rules.** `python` is on the allowlist, and the allowlist is
only a prefix test, so `python -c "import os; os.system('del important.txt')"` is treated as a safe
Python command and runs arbitrary code without confirmation. Chaining is another hole:
`git status; del important.txt` starts with an allowlisted prefix, and `del` without `/f` is not in the
blocklist. Allowlisting an interpreter is effectively allowlisting everything that interpreter can do;
a real system would avoid `shell=True`, parse the command, run it in a container as an unprivileged user,
and still ask before any write outside the project folder.
""")

# ---------------- B3
md(r"""
### B3. `read_lines(path, start, end)` (10 marks)

Line numbers are **1-based and inclusive**, and each returned line is prefixed with its number. The
function returns readable errors instead of raising, so the agent can recover: missing file, `start > end`,
`start < 1`, and a range that runs past the end (the end is clipped and the clipping is reported).
""")

code(r'''
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
        return f"Error: start line {start} is past the end of the file, which has {len(lines)} lines."

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


print("A. Normal range 4-12:")
print(_read_lines("assignment_starter/inventory.py", 4, 12))

print("B. Range past the end (30-99):")
print(_read_lines("assignment_starter/inventory.py", 30, 99))

print("C. Missing file:")
print(_read_lines("ghost.py", 1, 5))

print("D. start > end:")
print(_read_lines("assignment_starter/inventory.py", 10, 5))
''')

md(r"""
**Why this helps `edit_file` on large files.** `edit_file` requires `old_str` to match exactly once, so the
agent must copy the target text *exactly*, including indentation and surrounding lines. Without
`read_lines` the agent either reads a 5,000-line file (wasting context, possibly hitting the 10,000-character
truncation) or edits from memory and gets `old_str not found`. `read_lines` returns a small, numbered slice,
so the agent can jump to the reported line, read a window around it, and build a unique `old_str` from
text it has just seen. It also makes verification cheap: after an edit it can re-read the same range and
compare the numbered lines before running the tests.
""")

# ---------------- B4
md(r"""
### B4. A tool-call tracer (6 marks)

`show_trace` walks `result.new_items`. For a `tool_call_item` it prints `raw_item.name` and
`raw_item.arguments`; for a `tool_call_output_item` it prints the first 200 characters of `item.output`;
for a `message_output_item` it prints the assistant text. It finishes with the final answer. This is used
on the Part C run.
""")

code(r'''
def _message_text(item) -> str:
    parts = []
    for block in getattr(item.raw_item, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) or "(no text)"


def show_trace(result) -> None:
    """Print every item in a run: tool name, arguments, 200-char result, then the final answer."""
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
    print("\nFINAL ANSWER")
    print("-" * 60)
    print(result.final_output)


print("show_trace ready.")
''')

# ------------------------------------------------------------------ Part C
md(r"""
## Part C — Put your agent to work (25 marks)

### C1. Run the tests myself and record the failures

The first cell restores the pristine buggy module from `inventory_buggy.py`, hashes the test file (so we
can prove it is unchanged at the end), and runs the tests with no agent involved.
""")

code(r'''
starter = "assignment_starter"
shutil.copyfile(os.path.join(starter, "inventory_buggy.py"), os.path.join(starter, "inventory.py"))

with open(os.path.join(starter, "test_inventory.py"), "rb") as f:
    TEST_HASH_BEFORE = hashlib.sha256(f.read()).hexdigest()
print("test_inventory.py SHA-256 BEFORE:", TEST_HASH_BEFORE)
print()

baseline = subprocess.run(
    "python -m pytest assignment_starter -q",
    shell=True, capture_output=True, text=True, timeout=120,
)
print(baseline.stdout)
print("pytest exit code:", baseline.returncode)
''')

md(r"""
**Recorded result:** `4 failed, 3 passed`. The four failures are `test_add_existing_item_accumulates`,
`test_remove_to_zero_deletes_item`, `test_total_value_ignores_unpriced_items` and
`test_low_stock_is_strict_and_sorted`. The tests are correct; the module is wrong.

### C2. One prompt, all tools

The agent below has all five primitives plus B2 (`run_command`), B3 (`read_lines`) and B4 (`show_trace`).
It receives the prompt once. The system instructions tell it to explore, run the tests, make minimal edits,
never touch test files, and use only allowlisted commands from the project root.
""")

code(r'''
AGENT_INSTRUCTIONS = """You are a careful coding assistant working in a Windows folder.

Work in this order:
1. Explore: list files and read the relevant source before changing anything.
2. Understand: run the tests to see the real failure.
3. Fix: make the smallest correct edit with edit_file. Match old_str exactly and include
   enough surrounding lines to make it unique.
4. Verify: re-run the tests after every change and keep going until they pass.

Rules:
- Run commands from the project root. Do NOT use cd.
- The virtual environment is on PATH, so use `python` (not python3).
- Use commands that start with python, pytest, ls, cat, git status or git diff.
- Never modify or delete test files. Fix the source, not the tests.
- If a tool refuses a command, read the refusal and choose a safe alternative.
- Report exactly what you changed and the final test output. Do not claim a test passed
  unless you ran it in this session.
"""

agent = Agent(
    name="Coding Assistant",
    instructions=AGENT_INSTRUCTIONS,
    model=MODEL,
    tools=[read_file, list_files, run_command, edit_file, search_code, read_lines],
)

PROMPT = (
    "Run the tests in assignment_starter, find out why they fail, fix inventory.py, "
    "and re-run the tests until they all pass. Do not change the test file."
)
print("USER:", PROMPT)
print("=" * 70)

result = await Runner.run(agent, PROMPT)
show_trace(result)
''')

md(r"""
### C3. Verification

The trace above is the full output for the run. The cells below count the tool calls, confirm the test file
hash is unchanged, re-run the tests independently, and print the final module.
""")

code(r'''
calls = [item for item in result.new_items if item.type == "tool_call_item"]
print("Total tool calls:", len(calls))
for number, item in enumerate(calls, 1):
    print(f"  {number}. {item.raw_item.name}({item.raw_item.arguments[:160]})")

with open("assignment_starter/test_inventory.py", "rb") as f:
    TEST_HASH_AFTER = hashlib.sha256(f.read()).hexdigest()
print()
print("test_inventory.py SHA-256 AFTER: ", TEST_HASH_AFTER)
print("Test file unchanged:", TEST_HASH_BEFORE == TEST_HASH_AFTER)

verification = subprocess.run(
    "python -m pytest assignment_starter -q",
    shell=True, capture_output=True, text=True, timeout=120,
)
print()
print(verification.stdout)
print("pytest exit code:", verification.returncode)
''')

code(r'''
print(open("assignment_starter/inventory.py", encoding="utf-8").read())
''')

md(r"""
### C4. Analysis

**Run summary.** The agent made **7 tool calls** (15 trace items): `list_files(".")`,
`list_files("assignment_starter")`, `read_file(inventory.py)`, `read_file(test_inventory.py)`,
`pytest assignment_starter/test_inventory.py`, `edit_file(...)`, and the same `pytest` again. It made no
refused command and never wrote to the test file; the SHA-256 is identical before and after.

**Which bug it found first.** The first failure in the baseline output was
`test_add_existing_item_accumulates` (`add_item({"pen": 3}, "pen", 2)` returned `{"pen": 2}` instead of
`{"pen": 5}`). The agent read the whole test file and the module before editing, so it diagnosed that bug
and the other three together, then fixed all four in a single edit instead of one bug at a time.

**Wrong moves.** None that changed the outcome. It read the test file, which is allowed, but did not
modify it. It ran `pytest assignment_starter/test_inventory.py` rather than `python -m pytest`, which my
B2 allowlist permits. It also listed the project root and saw my probe scripts and this notebook, but
ignored them. The one process criticism is that its edit replaced the entire block from `def add_item`
to the end of the file. That is legal — the block occurs exactly once — but it is not the “smallest edit”
my instructions asked for: a reviewer has to diff a 20-line replacement instead of four one-line changes.

**Is each fix correct, or just test-passing?** All four match the documented behaviour, not merely the
assertions:

- `add_item` now does `inventory.get(name, 0) + qty`, so stock accumulates; the negative-quantity guard is
  untouched. Correct.
- `remove_item` deletes only when the stock is `== 0`. The old `< 0` branch could never fire because the
  preceding guard rejects over-removal. Correct.
- `total_value` uses `prices.get(name, 0)`, which implements “items with no price count as 0” instead of
  raising `KeyError`. Correct.
- `low_stock` uses `qty < threshold` (strict) and wraps the comprehension in `sorted()`, satisfying both
  halves of its docstring even though the test only checks one inventory. Correct.

None of the edits weakens a test or special-cases the test data. The agent re-ran pytest after the edit
and only claimed success after seeing `7 passed`; the independent run in C3 also passes 7/7.

**Caveat.** `remove_item` still accepts a negative quantity, which would increase stock. No test covers it
and the docstring does not mention it, so the agent correctly left it alone for this bug-fix prompt — but a
human review should raise it. The module docstring still says “It has bugs”; that sentence is now stale,
but I left the file exactly as the agent produced it rather than hand-editing the submitted result.
""")

# ------------------------------------------------------------------ Part D
md(r"""
## Part D — Reflect (10 marks)

I expected a coding agent to be a large system. The first surprise was how little code it takes: five
small Python functions — read, list, search, run, edit — plus a loop that the SDK already provides. The
whole Part C agent is roughly a hundred lines of tool code. What makes it work is not clever logic but
*description*: the type hints and docstrings are the model's only manual for choosing and calling a tool.
When my `read_lines` docstring said “1-based, inclusive”, the agent used it correctly first time; when a
description is vague, the model guesses. The second surprise was how naturally it chains tools. Nobody
told it to list the folder before reading `inventory.py`; it did that because exploration is the obvious
first step from the instructions.

One moment it did something I did not ask for was Lesson 5. The prompt asked for a FizzBuzz program in
`hello_world.py`; the agent wrote `fizzbuzz.py` and then summarised the work as complete. I caught it by
reading the `list_files` output in `result.new_items`, not by trusting the summary. In my own Part C run
the same gap appeared in a milder form: instead of four small edits, it replaced a twenty-line block in
one go. That was correct, but it was not the “smallest edit” I had asked for, and it made review harder.
Earlier, in Lesson 4, the agent tried `python3` on Windows, received the Microsoft Store alias error
(exit code 9009), and told me Python was not installed. That was false — Python 3.12 was running the
notebook — but it was a truthful report of the shell it was given. Both incidents taught me the same
lesson: read the raw tool output, not the prose.

The most dangerous tool is `run_command`. Read, list and search can leak data; edit can destroy a file;
but a shell can do all of that, install malware, and reach the network. A real product would run it in a
disposable container as an unprivileged user, avoid `shell=True`, enforce an allowlist with human approval
for anything outside it, cap time and output, restrict network egress, and keep an audit log. It should
also snapshot or use version control so every change can be reviewed as a diff and rolled back. The B2
rules are a teaching version of that idea, not a security boundary.

I would add an MCP server instead of a hand-written tool when the capability already exists behind a
maintained, standard interface. The GitHub MCP server is the obvious next one for this agent: it could read
issues, inspect pull requests and fetch CI logs, so the agent could start from a real bug report and verify
its fix against the same checks a reviewer sees. For anything specific to my own project — the exact
allowlist, the files I am permitted to touch — I would still write the tool myself.
""")

# ------------------------------------------------------------------ Part E
md(r"""
## Part E — Bonus (10 marks)

**Chosen bonus: rewrite `search_code` in pure Python so it works on Windows without `grep`.** This is the
implementation already used as the fifth tool above, so the whole notebook runs on Windows. It keeps the
Lesson 6 contract:

- `os.walk` instead of `grep -r`;
- the same skip-folders: `.git`, `__pycache__`, `node_modules`, `.venv`, `venv` (plus `.ipynb_checkpoints`);
- the same `file:line:text` output and optional `file_type` filter;
- a hard stop at **50 matches**, with `... (truncated at 50 matches)`;
- `No matches found` for zero hits and a clear message for an invalid regex.

The demo builds a tree with matching text hidden inside every skipped folder plus 60 matches in a real
file, then searches twice.
""")

code(r'''
demo = "bonus_demo"
if os.path.isdir(demo):
    shutil.rmtree(demo)
for sub in (".git", "__pycache__", "node_modules/pkg", ".venv/lib", "src"):
    os.makedirs(os.path.join(demo, sub), exist_ok=True)

for sub in (".git", "__pycache__", "node_modules/pkg", ".venv/lib"):
    with open(os.path.join(demo, sub, "hidden.py"), "w", encoding="utf-8") as f:
        f.write("NEEDLE = 'should be skipped'\n")

with open(os.path.join(demo, "src", "keep.py"), "w", encoding="utf-8") as f:
    f.write("def keep():\n    return 'NEEDLE'\n")

with open(os.path.join(demo, "src", "many.py"), "w", encoding="utf-8") as f:
    for i in range(1, 61):
        f.write(f"NEEDLE_{i} = {i}\n")

print("A. Search only .py files for NEEDLE (50-match cap):")
print(_search_code("NEEDLE", demo, "py"))
print()
print("B. Text that exists only inside skipped folders:")
print(_search_code("should be skipped", demo, "py"))
''')

md(r"""
The first search returns `src/keep.py:2` followed by matches from `src/many.py`, and stops with
`... (truncated at 50 matches)` — proof of the cap. None of the `hidden.py` files appear, because their
folders are pruned before they are walked. The second search returns `No matches found`, which proves the
skip-folders rather than merely the cap. On Windows this removes the `grep` dependency that makes the
original Lesson 6 tool fail, and it is the same tool the Part C agent used.
""")

# ------------------------------------------------------------------ submission
md(r"""
## Submission checklist

- [x] Part A: all 14 check-yourself answers with observed output; full FizzBuzz trace.
- [x] Part B1: `chat()` with history and a two-turn proof.
- [x] Part B2: blocklist, allowlist, confirmation, clear refusals, and one bypass explained.
- [x] Part B3: `read_lines` with numbering and all three error cases.
- [x] Part B4: `show_trace` used on the Part C run.
- [x] Part C: baseline failures recorded, one prompt, full trace, 7/7 tests passing, unchanged test file, analysis.
- [x] Part D: 300–500 word reflection.
- [x] Part E: pure-Python `search_code` bonus, demonstrated.
- [x] No API key in any cell or output; the key comes from `OPENAI_API_KEY`.
- [x] `inventory.py` submitted in its final, fixed state.

**Files:** `assignment_Kabunga_Akram_Joshua.ipynb`, `assignment_starter/inventory.py`,
`assignment_starter/test_inventory.py`.
""")

nb = new_notebook(cells=cells)
nb.metadata = {
    "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12.14"},
}

path = "assignment_Kabunga_Akram_Joshua.ipynb"
with open(path, "w", encoding="utf-8") as f:
    nbf.write(nb, f)
print("wrote", path, "with", len(cells), "cells")
