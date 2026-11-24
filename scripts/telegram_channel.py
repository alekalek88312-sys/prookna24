#!/usr/bin/env python3
"""Check access or publish an approved post in the ProOknaKrsk channel."""

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

CHANNEL = "@ProOknaKrsk"
BOT = "ProOknaKrskBot"


def request(token, method, **payload):
    endpoint = f"https://api.telegram.org/bot{token}/{method}"
    query = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(query, timeout=30) as response:
            result = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"Telegram {method}: HTTP {exc.code}.") from None
    except (URLError, TimeoutError, ValueError):
        raise RuntimeError(f"Telegram {method}: no valid response received.") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError(f"Telegram did not confirm {method}.")
    return result["result"]


def check_access(token):
    bot = request(token, "getMe")
    if bot.get("username", "").casefold() != BOT.casefold():
        raise ValueError(f"The token must belong to @{BOT}.")

    chat = request(token, "getChat", chat_id=CHANNEL)
    if chat.get("type") != "channel" or chat.get("username", "").casefold() != CHANNEL[1:].casefold():
        raise ValueError("Telegram did not confirm the target channel.")

    member = request(token, "getChatMember", chat_id=chat["id"], user_id=bot["id"])
    if member.get("status") != "administrator" or member.get("can_post_messages") is not True:
        raise ValueError(f"Give @{BOT} the Post Messages right in {CHANNEL}.")
    return chat["id"]


def post_details():
    if os.environ.get("TELEGRAM_CONFIRM") != "ПУБЛИКОВАТЬ":
        raise ValueError("To publish, explicitly enter ПУБЛИКОВАТЬ.")
    if os.environ.get("GITHUB_RUN_ATTEMPT", "1") != "1":
        raise ValueError("Check the channel before starting a new manual publish run.")

    text = os.environ.get("TELEGRAM_POST_TEXT", "").strip()
    photo_url = os.environ.get("TELEGRAM_PHOTO_URL", "").strip()
    limit = 1024 if photo_url else 4096
    if not text or len(text) > limit:
        raise ValueError(f"The post text must contain 1–{limit} characters.")
    if photo_url:
        parts = urlsplit(photo_url)
        if parts.scheme != "https" or not parts.hostname or parts.username is not None:
            raise ValueError("The photo must have a public HTTPS URL.")
        return "sendPhoto", {"photo": photo_url, "caption": text}
    return "sendMessage", {"text": text}


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise ValueError("Set the TELEGRAM_BOT_TOKEN repository secret.")

    mode = os.environ.get("TELEGRAM_MODE", "check")
    if mode == "check":
        check_access(token)
        print(f"@{BOT} can post to {CHANNEL}. No post was sent.")
        return
    if mode != "publish":
        raise ValueError("Allowed modes: check, publish.")

    method, payload = post_details()
    channel_id = check_access(token)
    message = request(token, method, chat_id=channel_id, **payload)
    message_id = message.get("message_id")
    if not isinstance(message_id, int) or message_id <= 0:
        raise RuntimeError("Check the channel to confirm whether the post appeared.")
    print(f"Telegram confirmed publication: https://t.me/{CHANNEL[1:]}/{message_id}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
