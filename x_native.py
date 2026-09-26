#!/usr/bin/env python3
"""
x_native.py — X/Twitter actions via native GraphQL API (HTTP only, NO BROWSER).

Pengganti rettiwt-api yang sudah mati (REST v1.1 di-deprecate X, semua balikin
{"errors":[{"code":34}]} -> wrapper lama print "{}" palsu).

Cookie dibaca dari ~/.hermes/.env_rettiwt (base64: twid;auth_token;ct0).
Query ID di-refresh otomatis dari bundle JS X bila ada yang 404.

Aksi yang didukung:
    like <tweet_id>
    unlike <tweet_id>
    repost <tweet_id>
    unrepost <tweet_id>
    reply <tweet_id> "<text>"
    verify-like <tweet_id>      # cek status like
    verify-repost <tweet_id>    # cek status repost
"""
import base64
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D"
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Query ID default (didapat dari bundle client-web X, Sep 2026).
QUERY_IDS = {
    "FavoriteTweet": "lI07N6Otwv1PhnEgXILM7A",
    "UnfavoriteTweet": "ZYKSe-w7KEslx3JhSIk5LA",
    "CreateRetweet": "mbRO74GrOvSfRcJnlMapnQ",
    "DeleteRetweet": "ZyZigVsNiFO6v1dEks1eWg",
    "CreateTweet": "GYdIGqVWfZNho79bQ2XDoA",
    "TweetDetail": "zoF7_t363wZyzylk-BLfZQ",
    "Viewer": "9t128XgFic52jPUEkJMf6w",
    "UserByScreenName": "KybxDj9RrADIITXlGG8kpw",
    "UserTweets": "jeAA-59Y9FL7FmjgBNIVPw",
    "DeleteTweet": "nxpZCY2K-I6QoFHAHeojFQ",
}

ENV_CANDIDATES = [
    os.path.join(os.getcwd(), ".env"),
    os.path.expanduser("~/.twitt.env"),
    os.path.expanduser("~/.hermes/.env_rettiwt"),
]
QUERY_CACHE = os.path.expanduser("~/.x_query_ids.json")


class XError(Exception):
    pass


# ---------------------------------------------------------------- credentials

def load_cookies():
    """Load X session cookies from environment variables or .env file."""
    # 1. Direct env vars
    auth_token = os.environ.get("TWITTER_AUTH_TOKEN") or os.environ.get("AUTH_TOKEN")
    ct0 = os.environ.get("TWITTER_CT0") or os.environ.get("CT0")
    twid = os.environ.get("TWITTER_TWID") or os.environ.get("TWID")

    # 2. Base64 encoded key from env
    raw_key = (
        os.environ.get("TWITTER_API_KEY")
        or os.environ.get("API_KEY")
        or os.environ.get("RETTIWT_API_KEY")
    )

    # 3. Search files
    if not (auth_token and ct0) and not raw_key:
        for path in ENV_CANDIDATES:
            if os.path.exists(path):
                try:
                    for line in open(path):
                        line = line.strip()
                        if line.startswith("AUTH_TOKEN="):
                            auth_token = line.split("=", 1)[1].strip()
                        elif line.startswith("CT0="):
                            ct0 = line.split("=", 1)[1].strip()
                        elif line.startswith("API_KEY=") or line.startswith("RETTIWT_API_KEY="):
                            raw_key = line.split("=", 1)[1].strip()
                    if (auth_token and ct0) or raw_key:
                        break
                except Exception:
                    continue

    if auth_token and ct0:
        c = {"auth_token": auth_token, "ct0": ct0}
        if twid:
            c["twid"] = twid
        return c

    if not raw_key:
        raise XError("X auth cookies not found. Set AUTH_TOKEN and CT0 or provide .env file")

    try:
        decoded = base64.b64decode(raw_key).decode("utf-8", errors="replace")
    except Exception as e:
        raise XError(f"Failed to decode base64 cookie: {e}")

    cookies = {}
    for part in decoded.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()

    missing = [k for k in ("auth_token", "ct0") if not cookies.get(k)]
    if missing:
        raise XError(f"Incomplete cookies, missing: {missing}")
    return cookies


def build_headers(cookies):
    return {
        "authorization": f"Bearer {BEARER}",
        "cookie": "; ".join(f"{k}={v}" for k, v in cookies.items()),
        "x-csrf-token": cookies.get("ct0", ""),
        "x-twitter-active-user": "yes",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-client-language": "en",
        "content-type": "application/json",
        "user-agent": UA,
        "origin": "https://x.com",
        "referer": "https://x.com/",
    }


def _ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


# ------------------------------------------------------------------- graphql

def gql_get(op, headers, variables, features=None):
    qid = QUERY_IDS[op]
    params = {"variables": json.dumps(variables)}
    if features:
        params["features"] = json.dumps(features)
    url = f"https://x.com/i/api/graphql/{qid}/{op}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers)
    return _do(req)


def gql_post(op, headers, variables, features=None, extra=None):
    qid = QUERY_IDS[op]
    body = {"variables": variables, "queryId": qid}
    if features:
        body["features"] = features
    if extra:
        body.update(extra)
    url = f"https://x.com/i/api/graphql/{qid}/{op}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    return _do(req)


def _do(req):
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ctx()) as r:
            txt = r.read().decode("utf-8", errors="replace")
            return r.status, (json.loads(txt) if txt.strip() else {})
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(txt) if txt.strip() else {}
        except Exception:
            return e.code, {"raw": txt[:300]}
    except Exception as e:
        return 0, {"error": str(e)}


def _graphql_error(status, data):
    """Ambil pesan error GraphQL yang bermakna (kode 344 dsb)."""
    if status == 200 and data.get("data") and not data.get("errors"):
        return None
    errs = data.get("errors") or []
    if errs:
        e = errs[0]
        code = (e.get("extensions") or {}).get("code") or e.get("code")
        msg = e.get("message", "unknown error")
        return {"code": code, "message": msg}
    if status != 200:
        return {"code": status, "message": f"HTTP {status}"}
    return {"code": "empty", "message": "respons kosong tanpa data"}


# ---------------------------------------------------------------- core action

FEATURES_TWEET = {
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}


def like(tweet_id, headers=None):
    """Like tweet. Return (ok, detail)."""
    h = headers or build_headers(load_cookies())
    status, data = gql_post("FavoriteTweet", h, {"tweet_id": str(tweet_id)})
    err = _graphql_error(status, data)
    if err:
        return False, err
    return data.get("data", {}).get("favorite_tweet") == "Done", data.get("data")


def unlike(tweet_id, headers=None):
    h = headers or build_headers(load_cookies())
    status, data = gql_post("UnfavoriteTweet", h, {"tweet_id": str(tweet_id)})
    err = _graphql_error(status, data)
    if err:
        return False, err
    return True, data.get("data")


def repost(tweet_id, headers=None):
    """Retweet. Return (ok, detail termasuk rest_id)."""
    h = headers or build_headers(load_cookies())
    status, data = gql_post("CreateRetweet", h, {"tweet_id": str(tweet_id)})
    err = _graphql_error(status, data)
    if err:
        return False, err
    res = (
        data.get("data", {})
        .get("create_retweet", {})
        .get("retweet_results", {})
        .get("result", {})
    )
    return bool(res.get("rest_id")), res


def unrepost(tweet_id, headers=None):
    h = headers or build_headers(load_cookies())
    status, data = gql_post("DeleteRetweet", h, {"source_tweet_id": str(tweet_id)})
    err = _graphql_error(status, data)
    if err:
        return False, err
    return True, data.get("data")


def reply(tweet_id, text, headers=None):
    """Reply ke tweet. Return (ok, detail). Kode 344 = limit harian."""
    h = headers or build_headers(load_cookies())
    variables = {
        "tweet_text": text,
        "reply": {"in_reply_to_tweet_id": str(tweet_id), "exclude_reply_user_ids": []},
        "media": {"media_entities": [], "possibly_sensitive": False},
        "semantic_annotation_ids": [],
    }
    status, data = gql_post("CreateTweet", h, variables, features=FEATURES_TWEET)
    err = _graphql_error(status, data)
    if err:
        return False, err
    res = data.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {})
    return bool(res.get("rest_id")), res


def post(text, headers=None):
    """Post standalone tweet. Return (ok, detail)."""
    h = headers or build_headers(load_cookies())
    variables = {
        "tweet_text": text,
        "media": {"media_entities": [], "possibly_sensitive": False},
        "semantic_annotation_ids": [],
    }
    status, data = gql_post("CreateTweet", h, variables, features=FEATURES_TWEET)
    err = _graphql_error(status, data)
    if err or not isinstance(data, dict):
        return False, err or {"message": "invalid data"}
    res = data.get("data", {}).get("create_tweet", {}).get("tweet_results", {}).get("result", {})
    return bool(res.get("rest_id")), res


def delete_tweet(tweet_id, headers=None):
    """Delete tweet. Return (ok, detail)."""
    h = headers or build_headers(load_cookies())
    status, data = gql_post("DeleteTweet", h, {"tweet_id": str(tweet_id)})
    err = _graphql_error(status, data)
    if err:
        return False, err
    return True, data.get("data") if isinstance(data, dict) else {}


def follow(target, headers=None):
    """Follow user. Target: screen_name or numeric user_id."""
    h = dict(headers or build_headers(load_cookies()))
    h["content-type"] = "application/x-www-form-urlencoded"
    t = str(target).strip()
    body = {"user_id": t} if t.isdigit() else {"screen_name": t.lstrip("@")}
    url = "https://x.com/i/api/1.1/friendships/create.json"
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(body).encode(), headers=h, method="POST"
    )
    status, data = _do(req)
    if status == 200:
        return True, data
    err = _graphql_error(status, data)
    return False, err


def unfollow(target, headers=None):
    """Unfollow user. Target: screen_name or numeric user_id."""
    h = dict(headers or build_headers(load_cookies()))
    h["content-type"] = "application/x-www-form-urlencoded"
    t = str(target).strip()
    body = {"user_id": t} if t.isdigit() else {"screen_name": t.lstrip("@")}
    url = "https://x.com/i/api/1.1/friendships/destroy.json"
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(body).encode(), headers=h, method="POST"
    )
    status, data = _do(req)
    if status == 200:
        return True, data
    err = _graphql_error(status, data)
    return False, err


def user_by_screen_name(screen_name, headers=None):
    """Get user profile via GraphQL UserByScreenName."""
    h = headers or build_headers(load_cookies())
    variables = {"screen_name": str(screen_name).lstrip("@"), "withSafetyModeUserFields": True}
    features = {
        "hidden_profile_subscriptions_enabled": True,
        "rweb_tipjar_consumption_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "highlights_tweets_tab_ui_enabled": True,
        "responsive_web_twitter_article_notes_tab_enabled": True,
        "subscriptions_feature_can_gift_premium": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    }
    status, data = gql_get("UserByScreenName", h, variables, features)
    err = _graphql_error(status, data)
    if err or not isinstance(data, dict):
        return None, err or {"message": "invalid data"}
    res = data.get("data", {}).get("user", {}).get("result", {})
    return res, None


def get_user_timeline_raw(user_id, count=20, cursor=None, headers=None):
    """Fetch user timeline via GraphQL UserTweets. Returns (data, next_cursor, err)."""
    h = headers or build_headers(load_cookies())
    variables = {
        "userId": str(user_id),
        "count": int(count),
        "includePromotedContent": False,
        "withQuickPromoteEligibilityTweetFields": False,
        "withVoice": False,
        "withV2Timeline": True,
    }
    if cursor:
        variables["cursor"] = str(cursor)
    status, data = gql_get("UserTweets", h, variables)
    err = _graphql_error(status, data)
    if err or not isinstance(data, dict):
        return None, None, err or {"message": "invalid data"}
    next_cursor = None
    try:
        timeline_obj = data.get("data", {}).get("user", {}).get("result", {}).get("timeline", {}).get("timeline", {})
        instr = timeline_obj.get("instructions", []) if isinstance(timeline_obj, dict) else []
        for ins in instr:
            for entry in ins.get("entries", []):
                if entry.get("content", {}).get("cursorType") == "Bottom":
                    next_cursor = entry.get("content", {}).get("value")
    except Exception:
        pass
    return data, next_cursor, None


def user_timeline_tweets(target, count=10, cursor=None, headers=None):
    """
    Get user's tweets as simplified dicts.
    Target: username or user_id.
    Returns: {"list": [{"id": ..., "fullText": ..., "createdAt": ...}], "next_cursor": ...}
    """
    h = headers or build_headers(load_cookies())
    target_str = str(target).strip()
    if target_str.isdigit():
        uid = target_str
    else:
        user_res, err = user_by_screen_name(target_str, h)
        if not user_res:
            return {"list": [], "error": str(err)}
        uid = user_res.get("rest_id")
    if not uid:
        return {"list": [], "error": "user_id tidak ditemukan"}

    data, next_cur, err = get_user_timeline_raw(uid, count=count, cursor=cursor, headers=h)
    if err or not isinstance(data, dict):
        return {"list": [], "error": str(err)}

    tweets = []
    try:
        timeline_obj = data.get("data", {}).get("user", {}).get("result", {}).get("timeline", {}).get("timeline", {})
        instr = timeline_obj.get("instructions", []) if isinstance(timeline_obj, dict) else []
        for ins in instr:
            for entry in ins.get("entries", []):
                item = entry.get("content", {}).get("itemContent", {})
                tr = item.get("tweet_results", {}).get("result", {})
                legacy = tr.get("legacy") or tr.get("tweet", {}).get("legacy")
                if legacy:
                    tid = tr.get("rest_id") or legacy.get("id_str")
                    tweets.append({
                        "id": tid,
                        "fullText": legacy.get("full_text", ""),
                        "createdAt": legacy.get("created_at", ""),
                        "likeCount": legacy.get("favorite_count", 0),
                        "retweetCount": legacy.get("retweet_count", 0),
                        "isRetweet": bool(legacy.get("retweeted_status_result")),
                    })
    except Exception as e:
        return {"list": tweets, "error": str(e)}

    return {"list": tweets, "next_cursor": next_cur}


def read_tweet_text(tweet_id, headers=None):
    """Read tweet details. Return formatted '@user: text' or 'Error'."""
    h = headers or build_headers(load_cookies())
    data, err = get_tweet_detail(tweet_id, h)
    if err or not isinstance(data, dict):
        return f"Error: {err.get('message', str(err)) if isinstance(err, dict) else str(err)}"
    legacy = _find_focal_legacy(data)
    if not legacy:
        return "Tweet not found"
    user = "?"
    for tr in _iter_tweet_results(data):
        if tr.get("rest_id") == str(tweet_id):
            u = tr.get("core", {}).get("user_results", {}).get("result", {})
            user = (
                u.get("core", {}).get("screen_name")
                or u.get("legacy", {}).get("screen_name")
                or "?"
            )
            break
    text = legacy.get("full_text", "")
    return f"@{user}: {text}"


# ------------------------------------------------------------- verification

def get_tweet_detail(tweet_id, headers=None):
    h = headers or build_headers(load_cookies())
    variables = {
        "focalTweetId": str(tweet_id),
        "with_rux_injections": False,
        "rankingMode": "Relevance",
        "includePromotedContent": True,
        "withCommunity": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withBirdwatchNotes": True,
        "withVoice": True,
    }
    features = {
        "rweb_video_timestamps_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_enhance_cards_enabled": False,
    }
    status, data = gql_get("TweetDetail", h, variables, features)
    err = _graphql_error(status, data)
    if err:
        return None, err
    return data, None


def whoami(headers=None):
    """Cek identitas + validitas cookie via query Viewer."""
    h = headers or build_headers(load_cookies())
    status, data = gql_get("Viewer", h, {})
    err = _graphql_error(status, data)
    if err:
        return None, err
    v = data.get("data", {}).get("viewer")
    if not v:
        return None, {"code": "no-viewer", "message": "cookie tidak valid / expired"}
    return v, None


def verify_like(tweet_id, headers=None):
    """Cek apakah tweet ini sudah di-like oleh akun kita."""
    data, err = get_tweet_detail(tweet_id, headers)
    if err:
        return None, err
    legacy = _find_focal_legacy(data)
    if not legacy:
        return None, {"code": "not-found", "message": "tweet tidak ditemukan"}
    # favorited = status like akun sendiri
    return bool(legacy.get("favorited")), None


def verify_repost(tweet_id, headers=None):
    data, err = get_tweet_detail(tweet_id, headers)
    if err:
        return None, err
    legacy = _find_focal_legacy(data)
    if not legacy:
        return None, {"code": "not-found", "message": "tweet tidak ditemukan"}
    return bool(legacy.get("retweeted")), None


def _iter_tweet_results(data):
    """Iterasi semua tweet_result dari respons TweetDetail (termasuk replies)."""
    try:
        instr = data["data"]["threaded_conversation_with_injections_v2"]["instructions"]
    except (KeyError, TypeError):
        return
    stack = [instr]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            tr = node.get("tweet_results", {}).get("result")
            if isinstance(tr, dict) and tr.get("legacy"):
                yield tr
            # masuk ke entries / moduleItems / items
            for key in ("entries", "moduleItems", "items", "content", "item", "itemContent"):
                if key in node:
                    stack.append(node[key])
            # replies nested di dalam tweet
            if "legacy" in node:
                for key in ("replies", "self_thread"):
                    if key in node:
                        stack.append(node[key])
        elif isinstance(node, list):
            stack.extend(node)


def find_my_reply(tweet_id, screen_name=None, headers=None):
    """Cari apakah akun kita sudah reply di thread ini. Return (found, replies)."""
    data, err = get_tweet_detail(tweet_id, headers)
    if err:
        return False, []
    replies = []
    seen = set()
    for tr in _iter_tweet_results(data):
        user = _screen_name(tr)
        txt = _full_text(tr)
        tid = tr.get("rest_id") or tr.get("legacy", {}).get("id_str")
        if not user or tid in seen:
            continue
        seen.add(tid)
        replies.append({"user": user, "text": txt[:120], "id": tid})
    if screen_name:
        return any(r["user"].lower() == screen_name.lower() for r in replies), replies
    return bool(replies), replies


def _screen_name(tweet_result):
    try:
        core = tweet_result.get("core", {})
        u = core.get("user_results", {}).get("result", {})
        return (
            u.get("core", {}).get("screen_name")
            or u.get("legacy", {}).get("screen_name")
        )
    except Exception:
        return None


def _full_text(tweet_result):
    try:
        note = tweet_result.get("note_tweet", {}).get("note_tweet_results", {}).get("result", {})
        if note.get("text"):
            return note["text"]
        return tweet_result.get("legacy", {}).get("full_text", "")
    except Exception:
        return ""


def _find_focal_legacy(data):
    """Ambil legacy object tweet utama dari respons TweetDetail."""
    try:
        instr = data["data"]["threaded_conversation_with_injections_v2"]["instructions"]
        for ins in instr:
            for entry in ins.get("entries", []) or []:
                t = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result")
                if t and t.get("legacy"):
                    return t["legacy"]
    except Exception:
        return None
    return None


# --------------------------------------------------------------- query IDs

def refresh_query_ids():
    """Ambil ulang query ID dari bundle JS X (kalau kena 404 'Query not found')."""
    try:
        req = urllib.request.Request("https://x.com/home", headers={"user-agent": UA})
        html = urllib.request.urlopen(req, timeout=25, context=_ctx()).read().decode(
            "utf-8", errors="replace"
        )
    except Exception as e:
        return False, f"gagal fetch x.com: {e}"

    bundles = set(re.findall(r'https://abs\.twimg\.com/[^"\']+?\.js', html))
    found = {}
    for b in list(bundles)[:25]:
        try:
            txt = urllib.request.urlopen(
                urllib.request.Request(b, headers={"user-agent": UA}),
                timeout=25, context=_ctx(),
            ).read().decode("utf-8", errors="replace")
        except Exception:
            continue
        for m in re.finditer(
            r'queryId:"([A-Za-z0-9_-]{15,})",operationName:"([A-Za-z0-9_]+)"', txt
        ):
            found[m.group(2)] = m.group(1)
        if len(found) > 30:
            break

    if not found:
        return False, "tidak ada query id ditemukan di bundle"

    QUERY_IDS.update({k: v for k, v in found.items() if k in QUERY_IDS or True})
    try:
        json.dump(found, open(QUERY_CACHE, "w"), indent=2)
    except Exception:
        pass
    return True, found


def load_cached_query_ids():
    if os.path.exists(QUERY_CACHE):
        try:
            data = json.load(open(QUERY_CACHE))
            QUERY_IDS.update(data)
            return True
        except Exception:
            return False
    return False


# ------------------------------------------------------------------- CLI

def _main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1

    cmd = argv[1]
    load_cached_query_ids()

    try:
        cookies = load_cookies()
        headers = build_headers(cookies)
    except XError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 1

    def out(ok, detail, extra=None):
        r = {"ok": bool(ok), "action": cmd, "detail": detail}
        if extra:
            r.update(extra)
        print(json.dumps(r))
        return 0 if ok else 1

    if cmd == "whoami":
        v, err = whoami(headers)
        return out(v is not None, v if v else err)

    if cmd in ("like", "unlike", "repost", "unrepost"):
        if len(argv) < 3:
            return out(False, {"message": "butuh tweet_id"})
        fn = {"like": like, "unlike": unlike, "repost": repost, "unrepost": unrepost}[cmd]
        ok, detail = fn(argv[2], headers)
        return out(ok, detail)

    if cmd == "reply":
        if len(argv) < 4:
            return out(False, {"message": "butuh tweet_id dan text"})
        ok, detail = reply(argv[2], argv[3], headers)
        return out(ok, detail)

    if cmd == "verify-like":
        ok, err = verify_like(argv[2], headers)
        if err:
            return out(False, err)
        return out(ok, {"liked": ok})

    if cmd == "verify-repost":
        ok, err = verify_repost(argv[2], headers)
        if err:
            return out(False, err)
        return out(ok, {"reposted": ok})

    if cmd == "verify-reply":
        found, replies = find_my_reply(argv[2], argv[3] if len(argv) > 3 else None, headers)
        return out(found, {"replies": replies[:5]})

    if cmd == "refresh-queries":
        ok, res = refresh_query_ids()
        return out(ok, res if not ok else {"count": len(res)})

    if cmd == "tweet-detail":
        data, err = get_tweet_detail(argv[2], headers)
        return out(data is not None, err if err else {"keys": list(data.keys())})

    if cmd == "follow":
        if len(argv) < 3:
            return out(False, {"message": "butuh target"})
        ok, detail = follow(argv[2], headers)
        return out(ok, detail)

    if cmd == "unfollow":
        if len(argv) < 3:
            return out(False, {"message": "butuh target"})
        ok, detail = unfollow(argv[2], headers)
        return out(ok, detail)

    if cmd == "read":
        if len(argv) < 3:
            return out(False, {"message": "butuh tweet_id"})
        txt = read_tweet_text(argv[2], headers)
        print(txt)
        return 0

    if cmd == "user":
        if len(argv) < 3:
            return out(False, {"message": "butuh screen_name"})
        res, err = user_by_screen_name(argv[2], headers)
        return out(res is not None, res if res else err)

    if cmd == "timeline":
        if len(argv) < 3:
            return out(False, {"message": "butuh target"})
        cnt = int(argv[3]) if len(argv) > 3 else 10
        cur = argv[4] if len(argv) > 4 else None
        res = user_timeline_tweets(argv[2], count=cnt, cursor=cur, headers=headers)
        print(json.dumps(res))
        return 0

    if cmd == "delete":
        if len(argv) < 3:
            return out(False, {"message": "butuh tweet_id"})
        ok, detail = delete_tweet(argv[2], headers)
        return out(ok, detail)

    if cmd == "post":
        if len(argv) < 3:
            return out(False, {"message": "butuh text"})
        ok, detail = post(argv[2], headers)
        return out(ok, detail)

    print(f"perintah tidak dikenal: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
