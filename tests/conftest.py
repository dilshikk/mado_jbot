"""Shared pytest configuration: forces a hermetic settings environment.

`bot.core.config.settings` is a process-wide singleton created once, on the
first `from bot.core.config import ...`. `Settings` reads from real OS
environment variables *and* the project's `.env` file, which on a deployed
server contains live production secrets (bot token, admin chat id, required
channel, Cloudflare AI credentials). Without this file, whichever test
module happens to import `bot.*` first "wins" and its values get cached for
every other test module in the same run — and any var no test file sets
(e.g. Cloudflare credentials, REQUIRED_CHANNEL) leaks straight from the real
`.env`, which previously caused tests to make a real network call to
Cloudflare and see production values instead of test defaults.

Setting everything here — with plain assignment, not `setdefault` — runs
before any `bot.*` module is imported by any test file (conftest.py is
loaded first by pytest), so it always wins over both real OS environment
variables and the `.env` file, guaranteeing a deterministic, credential-free
settings singleton for the whole test session.
"""

import os

os.environ["BOT_TOKEN"] = "test-token"
os.environ["ADMIN_IDS"] = "1,2"
os.environ["ADMIN_CHAT_ID"] = "1"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REQUIRED_CHANNEL"] = ""
os.environ["CLOUDFLARE_ACCOUNT_ID"] = ""
os.environ["CLOUDFLARE_API_TOKEN"] = ""
os.environ["AI_SCREENING_ENABLED"] = "false"
