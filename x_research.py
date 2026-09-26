#!/usr/bin/env python3
"""
x_research.py — X/Twitter tool bridge using x_native.py (GraphQL / Native HTTP, NO BROWSER).
Replaces deprecated rettiwt-api.
"""

import sys
import os
import json

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import x_native


def like(tweet_id):
    ok, detail = x_native.like(str(tweet_id))
    return json.dumps({"ok": ok, "action": "like", "tweet_id": str(tweet_id), "detail": detail})


def retweet(tweet_id):
    ok, detail = x_native.repost(str(tweet_id))
    return json.dumps({"ok": ok, "action": "retweet", "tweet_id": str(tweet_id), "detail": detail})


def follow(target):
    ok, detail = x_native.follow(str(target))
    return json.dumps({"ok": ok, "action": "follow", "target": str(target), "detail": detail})


def unfollow(target):
    ok, detail = x_native.unfollow(str(target))
    return json.dumps({"ok": ok, "action": "unfollow", "target": str(target), "detail": detail})


def post(text):
    ok, detail = x_native.post(str(text))
    return json.dumps({"ok": ok, "action": "post", "detail": detail})


def reply(tweet_id, text):
    ok, detail = x_native.reply(str(tweet_id), str(text))
    return json.dumps({"ok": ok, "action": "reply", "tweet_id": str(tweet_id), "detail": detail})


def read_tweet(tweet_id):
    return x_native.read_tweet_text(str(tweet_id))


def user_details(username):
    res, err = x_native.user_by_screen_name(str(username))
    if not res:
        return json.dumps({"error": str(err)})
    legacy = res.get("legacy") or {}
    core = res.get("core") or {}
    return json.dumps({
        "id": res.get("rest_id"),
        "userName": core.get("screen_name") or legacy.get("screen_name"),
        "name": core.get("name") or legacy.get("name"),
        "details": res
    })


def timeline(user_id, count=10):
    data = x_native.user_timeline_tweets(str(user_id), count=int(count))
    return json.dumps(data)


def search(query, count=10, days_back=7):
    return "No results"


def run_rettiwt(args):
    """Compatibility shim for legacy scripts calling x_research.run_rettiwt."""
    if not args:
        return "{}"
    cmd_type = args[0]
    if cmd_type == "tweet":
        sub = args[1] if len(args) > 1 else ""
        if sub == "like" and len(args) > 2:
            return like(args[2])
        elif sub == "retweet" and len(args) > 2:
            return retweet(args[2])
        elif sub in ("post", "reply") and len(args) > 2:
            if "-r" in args:
                idx = args.index("-r")
                tid = args[idx + 1] if len(args) > idx + 1 else ""
                txt = args[idx + 2] if len(args) > idx + 2 else ""
                return reply(tid, txt)
            return post(args[2])
        elif sub == "details" and len(args) > 2:
            return json.dumps({"fullText": read_tweet(args[2])})
    elif cmd_type == "user":
        sub = args[1] if len(args) > 1 else ""
        if sub == "details" and len(args) > 2:
            return user_details(args[2])
        elif sub == "timeline" and len(args) > 2:
            cnt = int(args[3]) if len(args) > 3 else 10
            return timeline(args[2], cnt)
        elif sub == "follow" and len(args) > 2:
            return follow(args[2])
        elif sub == "unfollow" and len(args) > 2:
            return unfollow(args[2])
    return "{}"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 x_research.py <command> [args...]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "search":
        q = sys.argv[2] if len(sys.argv) > 2 else "airdrop"
        n = sys.argv[3] if len(sys.argv) > 3 else "10"
        d = int(sys.argv[4]) if len(sys.argv) > 4 else 7
        print(search(q, n, d))
    elif cmd == "user":
        print(user_details(sys.argv[2]))
    elif cmd == "timeline":
        cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        print(timeline(sys.argv[2], cnt))
    elif cmd == "like":
        print(like(sys.argv[2]))
    elif cmd in ("retweet", "repost"):
        print(retweet(sys.argv[2]))
    elif cmd == "follow":
        print(follow(sys.argv[2]))
    elif cmd == "unfollow":
        print(unfollow(sys.argv[2]))
    elif cmd == "post":
        print(post(sys.argv[2]))
    elif cmd == "reply":
        print(reply(sys.argv[2], sys.argv[3]))
    elif cmd == "read":
        print(read_tweet(sys.argv[2]))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
