import asyncio
import json
import os
import re
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from claude_agent_sdk import (
    AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, PermissionResultAllow,
    PermissionResultDeny, ResultMessage, TextBlock, ToolUseBlock,
)

from .agent import ROOT, load_connectors
from .persona import CHAT_PROMPT

load_dotenv(ROOT / ".env")
app = FastAPI()
STATIC = Path(__file__).parent / "static"

# Tool names that only read are auto-approved; everything else asks the owner.
READ_ONLY = re.compile(r"(^|__|_)(get|list|read|search|query|find|show|fetch|describe|"
                       r"download|check|stats|analytics|balance|poll)", re.I)


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.websocket("/ws")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    pending: dict[str, asyncio.Future] = {}
    counter = 0

    async def can_use_tool(name, tool_input, context):
        nonlocal counter
        if READ_ONLY.search(name) and not re.search(
                r"(create|update|delete|send|share|trash|publish|launch|set|write|merge|push)",
                name, re.I):
            return PermissionResultAllow()
        counter += 1
        rid = str(counter)
        fut = asyncio.get_event_loop().create_future()
        pending[rid] = fut
        await ws.send_json({"type": "approval", "id": rid, "tool": name,
                            "input": json.dumps(tool_input, indent=2)[:1500]})
        ok = await fut
        return PermissionResultAllow() if ok else PermissionResultDeny(
            message="The owner denied this action.")

    try:
        servers = load_connectors()
    except SystemExit:
        servers = {}
    options = ClaudeAgentOptions(
        model=os.environ.get("MAXIMUS_MODEL", "claude-sonnet-5-5"),
        system_prompt=CHAT_PROMPT,
        mcp_servers=servers,
        allowed_tools=[],
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit"],
        can_use_tool=can_use_tool,
        max_turns=40,
    )

    async def run_turn(client, text):
        await client.query(text)
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        await ws.send_json({"type": "text", "text": b.text})
                    elif isinstance(b, ToolUseBlock):
                        await ws.send_json({"type": "tool", "name": b.name})
            elif isinstance(msg, ResultMessage):
                break
        await ws.send_json({"type": "done"})

    try:
        async with ClaudeSDKClient(options=options) as client:
            turn: asyncio.Task | None = None
            while True:
                data = await ws.receive_json()
                if data["type"] == "message" and (turn is None or turn.done()):
                    turn = asyncio.create_task(run_turn(client, data["text"]))
                elif data["type"] == "approval":
                    fut = pending.pop(data["id"], None)
                    if fut and not fut.done():
                        fut.set_result(bool(data["approved"]))
    except WebSocketDisconnect:
        for f in pending.values():
            if not f.done():
                f.set_result(False)
    except Exception as e:  # surface startup errors (e.g. missing API key) in the UI
        await ws.send_json({"type": "error", "text": str(e)})


def main():
    print("Maximus chat -> http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
