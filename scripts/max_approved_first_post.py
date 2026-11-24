#!/usr/bin/env python3
"""Send exactly one owner-approved MAX channel post via an opt-in file addition."""
import hashlib
import os
import sys
import urllib.parse
from pathlib import Path

from max_channel import DEFAULT_CHANNEL_ID, request

APPROVED_PATH = Path("max-posts/approved/first-winter-2026.txt")
APPROVED_SHA256 = "4184af071c0a5b81224a9f6bc39049a1113613e89ac82e7df5e025d2b00ed5cc"
EXPECTED_CHANNEL_ID = "-77027887534237"

def main():
    token = os.environ.get("MAX_BOT_TOKEN", "").strip()
    if not token:
        raise ValueError("MAX_BOT_TOKEN GitHub secret is unavailable")

    raw = APPROVED_PATH.read_text(encoding="utf-8")
    message = raw.rstrip("\n")
    if hashlib.sha256(message.encode("utf-8")).hexdigest() != APPROVED_SHA256:
        raise ValueError("Post content differs from the owner-approved exact text")
    if not (1 <= len(message) <= 4000):
        raise ValueError("Invalid message length")

    channel_id = os.environ.get("MAX_CHANNEL_ID", "").strip() or DEFAULT_CHANNEL_ID
    if channel_id != EXPECTED_CHANNEL_ID:
        raise ValueError("Unexpected MAX channel ID. No post sent.")

    chat = request("GET", f"/chats/{channel_id}", token)
    title = (chat.get("title") or chat.get("name") or "").casefold().replace(" ", "")
    if "проокна24" not in title:
        raise ValueError("Destination title not verified as ПроОкна24. No post sent.")
    if chat.get("type") not in (None, "channel"):
        raise ValueError("Destination is not a channel. No post sent.")

    # MAX returns the latest posts first. On a rerun, skip an already published message.
    recent = request("GET", "/messages?" + urllib.parse.urlencode(
        {"chat_id": channel_id, "count": 100}), token)
    if not isinstance(recent.get("messages"), list):
        raise RuntimeError("Could not verify recent posts, declining publication")
    for item in recent["messages"]:
        body = item.get("body") or {}
        existing = (body.get("text") or "").strip()
        if existing == message.strip():
            print("The approved post is already present in the channel. No duplicate was created.")
            return

    result = request("POST", "/messages?" + urllib.parse.urlencode(
        {"chat_id": channel_id}), token, {"text": message, "format": "markdown"})
    confirmed = result.get("message")
    if not isinstance(confirmed, dict):
        raise RuntimeError("MAX did not return a publication confirmation. Check channel before retry.")
    body = confirmed.get("body") or {}
    if not body.get("text"):
        raise RuntimeError("MAX replied without post text. Check channel before retry.")
    print("Published owner-approved first winter post in ПроОкна24.")
    print("Post ID:", body.get("mid") or confirmed.get("post_id") or "(not supplied)")
    print("Post link:", confirmed.get("url") or confirmed.get("link") or "(not supplied)")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Stopped safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
