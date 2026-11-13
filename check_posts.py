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
            return json.load(res)
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
            return res
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Discord Webhook エラー (HTTP {e.code}): {body}") from e


def fetch_latest_posts(username, token):
    url = f"/users/by/username/{username}?user.fields=id,username"
    user = api_get(url, token)
    user_id = user.get("data", {}).get("id")
    if not user_id:
        raise RuntimeError(f"ユーザーIDの取得に失敗しました: {username}")

    # 最新の投稿を最大5件取得。まるごと表示代
    tweets = api_get(
        f"/users/{user_id}/tweets?max_results=5&tweet.fields=created_at,text",
        token,
    )
    items = tweets.get("data", []) or []
    return [{"id": t["id"], "text": t.get("text", ""), "created_at": t.get("created_at")} for t in items]


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def format_time(created_at):
    if not created_at:
        return ""
    dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    jst = dt.astimezone(timezone.utc)  # device timezone
    return jst.strftime("%Y-%m-%d %H:%M:%S") + " JST"


def make_embed(author, text, created_at, url):
    return {
        "title": f"{author} の新規ポスト",
        "description": text,
        "url": url,
        "color": 0xFF0000,
        "timestamp": datetime.fromisoformat(created_at.replace("Z", "+00:00")).isoformat(),
        "footer": {"text": f"投稿時刻: {format_time(created_at)}"},
    }


def check_user(username, entry, token, webhook_url):
    posts = fetch_latest_posts(username, token)
    if not entry:
        # 初回: 最新の投稿を基準として保存するだけ
        if posts:
            entry = {"seen_id": posts[0]["id"]}
            print(f"[{username}] 初回基準登録: {posts[0]['id']}")
        else:
            entry = {"seen_id": None}
            print(f"[{username}] 初回基準登録: 投稿なし")
        return entry

    seen_id = entry.get("seen_id")
    if seen_id is None:
        print(f"[{username}] seen_id なし: 基準登録しません")
        return entry

    new_posts = [p for p in posts if p["id"] > seen_id]
    if not new_posts:
        print(f"[{username}] 新規ポストなし")
        return entry

    # 古い順に Discord へ送る
    for post in reversed(new_posts):
        url = f"https://x.com/{username}/status/{post['id']}"
        print(f"[{username}] 新規ポスト送信: {post['id']}")
        embed = make_embed(username, post["text"], post.get("created_at"), url)
        post_to_discord(
            webhook_url,
            {"username": "公式ポスト検知", "embeds": [embed]},
        )
        time.sleep(1)

    entry = {"seen_id": posts[0]["id"]}
    return entry


def main():
    token = os.environ.get("X_BEARER_TOKEN")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    usernames = [u.strip() for u in os.environ.get("X_USERNAMES", DEFAULT_USERNAMES).split(",") if u.strip()]
    missing = [k for k, v in [("X_BEARER_TOKEN", token), ("DISCORD_WEBHOOK_URL", webhook_url)] if not v]
    if missing:
        raise RuntimeError(f"必要な環境変数が設定されていません: {', '.join(missing)}")

    state = load_state()
    changed = False
    for username in usernames:
        entry = state.get(username)
        new_entry = check_user(username, entry, token, webhook_url)
        if new_entry != entry:
            state[username] = new_entry
            changed = True

    if changed:
        save_state(state)
        print("state.jsonを保存しました")
    else:
        print("変更なし")

    return 0


if __name__ == "__main__":
    sys.exit(main())
