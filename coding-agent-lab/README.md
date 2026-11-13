# Coding Agent Lab

A small coding agent built from scratch with the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python): an LLM in a loop with **read, list, search, run and edit** tools, plus conversation memory, a safety layer around the shell, range-based file reading, and a tool-call tracer.

The project was built for the *Prompt Engineering — Agentic Programming* assignment: explain the agent loop, harden it, and use it to repair a buggy Python module without touching the tests.

## Highlights

- **Five core primitives** — `read_file`, `list_files`, `search_code`, `run_command`, `edit_file` — plus `read_lines` for precise edits in large files.
- **Conversation memory** — a `chat()` loop that carries history between turns with `result.to_input_list()`.
- **Safer shell** — blocklist, allowlist and `Allow this command? [y/N]` confirmation, with explicit refusals the model can read and recover from.
- **Pure-Python search** — `os.walk` + `re`, so it works on Windows without `grep` (the Part E bonus).
- **Full traceability** — `show_trace(result)` prints every tool call, its arguments, the first 200 characters of each result, and the final answer.
- **Real repair run** — the agent fixes four seeded bugs in an inventory module in **7 tool calls** and gets **7/7 tests passing**, leaving the test file byte-for-byte unchanged.

## How the agent loop works

```
user message
    │
    ▼
  LLM (system prompt + tool schemas + history)
    │
    ├── text ──────────────────────────────► final answer
    │
    └── tool call
            │
            ▼
      Python function  (read / list / search / run / edit)
            │
            ▼
      tool result  ──► appended to the conversation ──► LLM again
```

A coding agent is not a special kind of model. It is a normal model, a loop, and a small set of well-described functions.

## Results

Part C starts from a module with four bugs (`4 failed, 3 passed`) and gives the agent a single prompt:

> Run the tests in `assignment_starter`, find out why they fail, fix `inventory.py`, and re-run the tests until they all pass. Do not change the test file.

| Metric | Result |
|---|---|
| Baseline | 4 failed, 3 passed |
| Tool calls | 7 |
| Bugs fixed | 4 (accumulate stock, delete at zero, missing prices, strict sorted low-stock) |
| Final test run | **7 passed** |
| Test file | SHA-256 identical before and after |
| Wrong moves | none affecting the result; one non-minimal edit |

The full trace is saved in the notebook, so the claim can be checked rather than trusted.

## Repository layout

| Path | Description |
|---|---|
| `assignment_Kabunga_Akram_Joshua.ipynb` | Main deliverable: Parts A–E, executed with saved outputs |
| `assignment_starter/inventory.py` | Final fixed inventory module |
| `assignment_starter/inventory_buggy.py` | Pristine buggy copy used to reset Part C |
| `assignment_starter/test_inventory.py` | Tests (never modified) |
| `agent_core.py` | Standalone version of the complete toolset, used for testing outside Jupyter |
| `build_notebook.py` | Script that generates the notebook |
| `observations.py` | Collects the real outputs quoted in Part A |
| `submission/` | Local packaging output (zip + HTML preview); git-ignored |
| `README.md`, `requirements.txt`, `.gitignore` | Project docs and environment |

> The remaining `*_probe.py` files are small exploratory scripts used while writing the explanations. They are not needed to run the notebook.

## Assignment map

| Part | Topic | Marks |
|---|---|---|
| A | Explain the loop; answer every check-yourself question; trace the FizzBuzz run | 20 |
| B1 | Conversation memory (`chat()` + proof) | 10 |
| B2 | Safer `run_command` (blocklist / allowlist / confirmation) | 10 |
| B3 | `read_lines(path, start, end)` | 10 |
| B4 | Tool-call tracer | 6 |
| C | Use the agent to fix `inventory.py` and analyse the run | 25 |
| D | Reflection | 10 |
| E | Bonus: pure-Python `search_code` | +10 |

## Quick start

Requires Python 3.10+ (tested on 3.12.14).

```powershell
git clone <your-repo-url>
cd coding-agent-lab

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

# Never hard-code the key in the notebook.
$env:OPENAI_API_KEY = "<your-key>"

jupyter lab assignment_Kabunga_Akram_Joshua.ipynb
```

On macOS/Linux use `source .venv/bin/activate` and `export OPENAI_API_KEY=...`.

The notebook is set to `gpt-5.4-mini`. If that model is not available on your account, change `MODEL` in the setup cell.

## Running the tests

```bash
python -m pytest assignment_starter -q
```

Expected:

```text
.......                                                                  [100%]
7 passed
```

To reproduce the full before-and-after, run the notebook from top to bottom. Part C restores `inventory.py` from `inventory_buggy.py`, so it always starts from the four failures.

## Safety model

`run_command` applies its policy in this order:

1. **Blocklist** — refuses `rm -rf`, `sudo`, `shutdown`, `mkfs`, `del /f`, `rd /s`, `curl | sh`, `wget | sh`, and similar patterns. Checked first, so `git status; rm -rf /` is still refused.
2. **Allowlist** — `python`, `pytest`, `ls`, `cat`, `git status`, `git diff` and friends run immediately.
3. **Confirmation** — anything else asks `Allow this command? [y/N]` and runs only on `y`.
4. **Clear refusal** — every rejection returns a message explaining which rule fired and what to do instead.

### Known limitations

- The allowlist is a prefix test, so `python -c "..."` is effectively unrestricted. Allowlisting an interpreter means allowlisting everything it can do.
- `shell=True` is convenient and unsafe for untrusted input; a production system should parse commands or use a sandbox.
- In a non-interactive run, commands that need confirmation are refused rather than hanging.
- `remove_item` accepts a negative quantity (untested, outside the assignment's scope).
- The module docstring still says the module “has bugs”; it was left exactly as the agent produced it.

### What a production version would add

A disposable container, an unprivileged user, no `shell=True`, network egress rules, time and output caps, an audit log, and a git checkpoint so every edit can be reviewed as a diff and rolled back.

## Notes

- The notebook reads the API key only from `OPENAI_API_KEY`; no key is stored in any cell, output, or committed file.
- Part A quotes outputs that were actually produced against `gpt-5.4-mini`, including a live Context7 MCP lookup.
- This repository is coursework for *Prompt Engineering — Agentic Programming*.
