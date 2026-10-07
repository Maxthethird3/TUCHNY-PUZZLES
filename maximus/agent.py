import asyncio
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from .persona import SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parent.parent


def load_connectors() -> dict:
    path = ROOT / "connectors.json"
    if not path.exists():
        print("No connectors.json found - Maximus will have nothing to review.\n"
              "Copy connectors.example.json to connectors.json first.", file=sys.stderr)
        sys.exit(1)
    raw = path.read_text()
    raw = re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), raw)
    servers = json.loads(raw)
    return {k: v for k, v in servers.items() if not k.startswith("_")}


async def run_report(period: str) -> str:
    servers = load_connectors()
    options = ClaudeAgentOptions(
        model=os.environ.get("MAXIMUS_MODEL", "claude-sonnet-5-5"),
        system_prompt=SYSTEM_PROMPT,
        mcp_servers=servers,
        # Read-only guardrail: allow only MCP tools, no shell/file edits.
        allowed_tools=[f"mcp__{name}" for name in servers],
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit"],
        max_turns=40,
    )
    prompt = (f"Today is {date.today():%Y-%m-%d}. Review my activity for: {period}. "
              "Use every connector available, then write the report.")
    report = ""
    async for msg in query(prompt=prompt, options=options):
        if isinstance(msg, ResultMessage) and msg.result:
            report = msg.result
    return report


def main() -> None:
    load_dotenv(ROOT / ".env")
    period = " ".join(sys.argv[1:]) or "the last 24 hours"
    report = asyncio.run(run_report(period))
    out = ROOT / "reports" / f"maximus-{date.today():%Y-%m-%d}.md"
    out.write_text(report)
    print(report)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
