# Maximus

Your first AI agent. Maximus reviews your recent activity across connected
tools (GitHub, Google Calendar/Drive, etc., via MCP) and writes you a report.
It is **read-only** by design.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                       # add ANTHROPIC_API_KEY
cp connectors.example.json connectors.json # add the connectors you want
python -m maximus "the last 7 days"
```
Reports are saved to `reports/`.

## Limits (honest notes)
- Maximus can see what its connectors expose. There is no public API for
  reading your claude.ai chat history, so it can't see those conversations.
  Claude Code sessions can be added later by pointing it at `~/.claude/projects`.
- It only reports what tools return; failed connectors are listed under Coverage.

## Roadmap
1. Schedule it daily (cron / GitHub Action) and email or Drive-save the report.
2. Add more connectors (Supabase, Shopify, Metricool, vidIQ).
3. Add memory so reports compare against previous days.
