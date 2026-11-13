#!/usr/bin/env python3
"""
X（旧Twitter）公式アカウントの新規ポスト検知 → Discord Webhook 通知

GitHub Actions 上で定期実行されることを想定した、標準ライブラリのみの
小さなプログラムです。

必要な環境変数（GitHub の Secrets に登録する）:
  X_BEARER_TOKEN       X API の Bearer Token
  DISCORD_WEBHOOK_URL  Discord チャンネルの Webhook URL
  X_USERNAMES          監視するアカウント（カンマ区切り、@なし）
                       未設定の場合は OnceHuman_JP のみ

状態は state.json に保存します:
  - 初回実行時は「基準登録」だけを行い、既存のポストは流しません。
  - 2回目以降、新しいポストだけを古い順に Discord へ送ります。
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_BASE = "https://api.x.com/2"
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
DEFAULT_USERNAMES = "OnceHuman_JP"


def api_get(path, token):
    req = urllib.request.Request(
        API_BASE + path,
        headers={"Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"X API エラー (HTTP {e.code}): {body}") from e


def post_to_discord(webhook_url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord Webhook エラー (HTTP {e.code}): {body}") from e


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_embed(username, display_name, tweet, media_by_key):
    text = tweet.get("text", "")
    if len(text) > 4000:
        text = text[:4000] + "…"
    url = f"https://x.com/{username}/status/{tweet['id']}"
    embed = {
        "title": f"{display_name}（@{username}）の新規ポスト",
        "description": text,
        "url": url,
        "color": 0x1D9BF0,
    }
    for key in tweet.get("attachments", {}).get("media_keys", []):
        media = media_by_key.get(key, {})
        if media.get("type") == "photo" and media.get("url"):
            embed["image"] = {"url": media["url"]}
            break
        if media.get("type") in ("video", "animated_gif") and media.get("preview_image_url"):
            embed["image"] = {"url": media["preview_image_url"]}
            break
    return embed


def check_user(username, entry, token, webhook_url):
    """1アカウント分をチェックし、新規ポストがあれば Discord へ送る。"""
    if not entry.get("id"):
        res = api_get(f"/users/by/username/{username}", token)
        if "data" not in res:
            print(f"[{username}] ユーザーが見つかりませんでした")
            return
        entry["id"] = res["data"]["id"]
        entry["display_name"] = res["data"].get("name", username)
        print(f"[{username}] ユーザーID を登録しました: {entry['id']}")

    user_id = entry["id"]
    display_name = entry.get("display_name", username)
    query = (
        f"/users/{user_id}/tweets?max_results=5&exclude=replies"
        "&tweet.fields=created_at"
        "&expansions=attachments.media_keys"
        "&media.fields=type,url,preview_image_url"
    )
    res = api_get(query, token)
    tweets = sorted(res.get("data", []), key=lambda t: int(t["id"]))
    if not tweets:
        print(f"[{username}] 取得できたポストがありません")
        return

    last_seen = entry.get("last_seen_id")
    if last_seen is None:
        entry["last_seen_id"] = tweets[-1]["id"]
        print(f"[{username}] 初回実行: 基準を最新ポスト {tweets[-1]['id']} に設定しました")
        return

    media_by_key = {
        m["media_key"]: m for m in res.get("includes", {}).get("media", [])
    }
    new_tweets = [t for t in tweets if int(t["id"]) > int(last_seen)]
    if not new_tweets:
        print(f"[{username}] 新規ポストなし")
        return

    for tweet in new_tweets:
        embed = build_embed(username, display_name, tweet, media_by_key)
        post_to_discord(
            webhook_url,
            {"username": "公式ポスト検知", "embeds": [embed]},
        )
        entry["last_seen_id"] = tweet["id"]
        print(f"[{username}] 投稿しました: https://x.com/{username}/status/{tweet['id']}")
        time.sleep(1)


def main():
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    raw_names = os.environ.get("X_USERNAMES") or DEFAULT_USERNAMES
    usernames = [
        u.strip().lstrip("@") for u in raw_names.split(",") if u.strip()
    ]

    if not token:
        print("エラー: 環境変数 X_BEARER_TOKEN が設定されていません", file=sys.stderr)
        return 1
    if not webhook_url:
        print("エラー: 環境変数 DISCORD_WEBHOOK_URL が設定されていません", file=sys.stderr)
        return 1
    if not usernames:
        print("エラー: 監視アカウントが空です", file=sys.stderr)
        return 1

    state = load_state()
    users = state.setdefault("users", {})
    for username in usernames:
        entry = users.setdefault(username, {})
        check_user(username, entry, token, webhook_url)

    # チェック時刻を毎回更新する（state.json が変わることで
    # リポジトリが活動中になり、スケジュールの自動無効化を防ぐ）
    state["last_check_utc"] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    print("完了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
