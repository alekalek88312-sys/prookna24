#!/usr/bin/env python3
"""Minimal and deliberately manual MAX channel publisher. No delete/edit methods."""
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = "https://platform-api2.max.ru"

def request(method, path, token, payload=None):
    url = ROOT + path
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=35) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not print response bodies or credentials; API error body may contain sensitive details.
        raise RuntimeError(f"MAX API responded with HTTP {exc.code}") from None

def main():
    token = os.getenv("MAX_BOT_TOKEN", "").strip()
    mode = os.getenv("MAX_MODE", "check").strip()
    channel_id = os.getenv("MAX_CHANNEL_ID", "").strip()
    if not token:
        raise ValueError("Repository secret MAX_BOT_TOKEN is missing.")
    if mode == "check":
        bot = request("GET", "/me", token)
        print("MAX API authentication OK. Bot name:", bot.get("first_name") or bot.get("name") or "(unknown)")
        if channel_id:
            if not re.fullmatch(r"-?\\d{1,20}", channel_id):
                raise ValueError("MAX_CHANNEL_ID must be a numeric identifier")
            request("GET", f"/chats/{channel_id}/members/me", token)
            print("Configured channel membership is accessible.")
        else:
            # Development-only, one short read. Do not print events or user/message data.
            result = request("GET", "/updates?timeout=0&limit=20", token)
            found = set()
            for event in result.get("updates", []):
                if event.get("update_type") in ("bot_added", "bot_admin_permissions_changed"):
                    if event.get("is_channel") is True and event.get("chat_id") is not None:
                        found.add(str(event["chat_id"]))
            if found:
                print("Candidate channel IDs from recent bot events:", ", ".join(sorted(found)))
                print("Save the correct ID as GitHub Actions secret MAX_CHANNEL_ID before publishing.")
            else:
                print("No channel ID in the recent event. MAX requires chat_id from bot_added/subscription events.")
        print("Check completed. No post was sent.")
        return
    if mode != "publish":
        raise ValueError("Unknown mode; allowed: check, publish")
    text = os.getenv("MAX_POST_TEXT", "").strip()
    confirmation = os.getenv("MAX_CONFIRM", "")
    if confirmation != "ПУБЛИКОВАТЬ":
        raise ValueError("To publish, explicitly enter ПУБЛИКОВАТЬ")
    if not re.fullmatch(r"-?\\d{1,20}", channel_id):
        raise ValueError("Set valid numeric MAX_CHANNEL_ID as a repository secret")
    if not text or len(text) > 4000:
        raise ValueError("The post must contain 1–4000 characters")
    result = request("POST", "/messages?" + urllib.parse.urlencode({"chat_id": channel_id}),
                     token, {"text": text})
    if result.get("success") is False or not isinstance(result.get("message"), dict):
        raise RuntimeError("MAX API did not confirm publication")
    print("MAX confirmed publication. A new post was created; no existing content modified.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Stopped safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
