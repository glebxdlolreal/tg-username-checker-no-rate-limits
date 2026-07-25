#!/usr/bin/env python3
import re
import sys
import time
import argparse
import requests

BASE = "https://fragment.com"

METHODS = [
    {
        "id": "stars_gift",
        "referer": "/stars/buy?quantity=50",
        "body": lambda u: f"query={u}&quantity=&method=searchStarsRecipient",
    },
    {
        "id": "premium_gift",
        "referer": "/premium/gift",
        "body": lambda u: f"query={u}&months=12&method=searchPremiumGiftRecipient",
    },
    {
        "id": "stars_giveaway",
        "referer": "/stars/giveaway?stars=500",
        "body": lambda u: f"query={u}&quantity=&method=searchStarsGiveawayRecipient",
    },
    {
        "id": "premium_giveaway",
        "referer": "/premium/giveaway",
        "body": lambda u: (
            f"query={u}&quantity=&months=12&method=searchPremiumGiveawayRecipient"
        ),
    },
    {
        "id": "ads_topup",
        "referer": "/ads/topup",
        "body": lambda u: f"query={u}&method=searchAdsTopupRecipient",
    },
]

HEADERS_TEMPLATE = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": BASE,
    "priority": "u=1, i",
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "x-requested-with": "XMLHttpRequest",
}

MSG_ASSIGNED_USER = "please enter a username assigned to a user"
MSG_ASSIGNED_CHANNEL = "please enter a username assigned to a channel"
MSG_NOT_FOUND_USER = "no telegram users found"
MSG_NOT_FOUND_CHANNEL = "no telegram channels found"
MSG_PREMIUM_ALREADY = "already subscribed to telegram premium"
MSG_NO_STARS = "can't gift telegram stars"
MSG_NO_FUNDS = "can't add funds"


def parse_ajinit(html):
    m = re.search(r'"apiUrl":"([^"]+)"', html)
    if not m:
        return None, None
    ver_m = re.search(r'"version":(\d+)', html)
    return (ver_m.group(1) if ver_m else "?"), m.group(1)


def extract_dc(photo):
    m = re.search(r"cdn(\d+)\.telesco\.pe", photo or "")
    return m.group(1) if m else "?"


def has_avatar(photo):
    if not photo:
        return False
    return "data:image/svg+xml" not in photo


def init_session():
    s = requests.Session()
    r = s.get(
        BASE,
        headers={
            "user-agent": HEADERS_TEMPLATE["user-agent"],
            "accept-language": "ru-RU,ru;q=0.9",
        },
        timeout=15,
    )
    version, api_url = parse_ajinit(r.text)
    if not api_url:
        print("[-] Failed to parse API URL from fragment.com")
        sys.exit(1)
    api_url = api_url.replace("\\/", "/")
    return s, version, api_url


def check_username(session, api_url, username):
    results = {}
    for m in METHODS:
        headers = {**HEADERS_TEMPLATE, "referer": f"{BASE}{m['referer']}"}
        try:
            r = session.post(
                f"{BASE}{api_url}",
                headers=headers,
                data=m["body"](username),
                timeout=15,
            )
            results[m["id"]] = r.json()
        except Exception as e:
            results[m["id"]] = {"_error": str(e)}
    return results


def analyze(results):
    name = "-"
    dc = "?"
    avatar = False
    is_channel = None
    premium = False
    exists = False
    stars_ok = False
    premium_ok = False
    ads_ok = False

    user_signals = 0
    channel_signals = 0

    for mid, data in results.items():
        if "_error" in data:
            continue

        err = (data.get("error") or "").lower()
        found = data.get("found")

        if found:
            exists = True
            n = found.get("name")
            if n:
                name = n
            photo = found.get("photo", "")
            if photo:
                d = extract_dc(photo)
                if d != "?":
                    dc = d
                if has_avatar(photo):
                    avatar = True

        if found and mid in ("stars_gift", "premium_gift", "ads_topup"):
            user_signals += 1
        elif found and mid in ("stars_giveaway", "premium_giveaway"):
            channel_signals += 1

        if MSG_ASSIGNED_CHANNEL in err:
            exists = True
            user_signals += 1
        elif MSG_ASSIGNED_USER in err:
            exists = True
            channel_signals += 1
        elif MSG_PREMIUM_ALREADY in err:
            exists = True
            premium = True
        elif MSG_NO_STARS in err:
            exists = True
        elif MSG_NO_FUNDS in err:
            exists = True
        elif MSG_NOT_FOUND_USER not in err and MSG_NOT_FOUND_CHANNEL not in err and err:
            exists = True

        if mid == "stars_gift" and found:
            stars_ok = True
        elif mid == "premium_gift" and found:
            premium_ok = True
        elif mid == "ads_topup" and found:
            ads_ok = True

    if is_channel is None:
        is_channel = channel_signals > user_signals

    return {
        "exists": exists,
        "name": name,
        "dc": dc,
        "avatar": avatar,
        "is_channel": is_channel,
        "premium": premium,
        "stars_ok": stars_ok,
        "premium_ok": premium_ok,
        "ads_ok": ads_ok,
    }


def print_result(username, info):
    s = "Taken" if info["exists"] else "Available"
    ca = "CH" if info["is_channel"] else "US"
    pr = "YES" if info["premium"] else "NO"
    st = "YES" if info["stars_ok"] else ("BLOCK" if info["exists"] else "NO")
    pg = "YES" if info["premium_ok"] else ("BLOCK" if info["exists"] else "NO")
    ad = "YES" if info["ads_ok"] else ("BLOCK" if info["exists"] else "NO")
    av = "YES" if info["avatar"] else "NO"

    full = "+" + "-" * 60 + "+"
    mid = "+" + "-" * 11 + "+" + "-" * 48 + "+"
    print(full)
    print(f"| @{username:<58} |")
    print(mid)
    print(f"| Status     | {s:<46} |")
    print(f"| Name       | {info['name']:<46} |")
    print(f"| DC         | {info['dc']:<46} |")
    print(f"| Avatar     | {av:<46} |")
    print(f"| Channel    | {ca:<46} |")
    print(f"| Premium    | {pr:<46} |")
    print(f"| Stars      | {st:<46} |")
    print(f"| Prem.Gift  | {pg:<46} |")
    print(f"| Gram       | {ad:<46} |")
    print(mid)


def print_table(results_list):
    print()
    sep = (
        "+"
        + "-" * 20
        + "+"
        + "-" * 7
        + "+"
        + "-" * 20
        + "+"
        + "-" * 4
        + "+"
        + "-" * 7
        + "+"
        + "-" * 8
        + "+"
        + "-" * 8
        + "+"
        + "-" * 6
        + "+"
        + "-" * 6
        + "+"
        + "-" * 6
        + "+"
    )
    h = f"|{'Username':>20}|{'Status':>7}|{'Name':>20}|{'DC':>4}|{'Avatar':>7}|{'Channel':>8}|{'Premium':>8}|{'Stars':>6}|{'Prem':>6}|{'Gram':>6}|"
    print(sep)
    print(h)
    print(sep)
    for username, info in results_list:
        st = "Taken" if info["exists"] else "Available"
        ch = "CH" if info["is_channel"] else "US"
        pr = "YES" if info["premium"] else "NO"
        av = "YES" if info["avatar"] else "NO"
        sg = "YES" if info["stars_ok"] else ("BLOCK" if info["exists"] else "NO")
        pg = "YES" if info["premium_ok"] else ("BLOCK" if info["exists"] else "NO")
        ad = "YES" if info["ads_ok"] else ("BLOCK" if info["exists"] else "NO")
        nm = info["name"] if len(info["name"]) <= 18 else info["name"][:15] + "..."
        print(
            f"|{username:>20}|{st:>7}|{nm:>20}|{info['dc']:>4}|{av:>7}|{ch:>8}|{pr:>8}|{sg:>6}|{pg:>6}|{ad:>6}|"
        )
    print(sep)


def read_usernames(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(
        description="Telegram Username Checker via fragment.com"
    )
    parser.add_argument(
        "usernames", nargs="*", help="Username(s) to check (with or without @)"
    )
    parser.add_argument("-f", "--file", help="File with usernames (one per line)")
    parser.add_argument(
        "-d", "--delay", type=float, default=0.5, help="Delay between checks in seconds"
    )
    args = parser.parse_args()

    usernames = []
    if args.file:
        usernames.extend(read_usernames(args.file))
    if args.usernames:
        usernames.extend(args.usernames)

    print("Telegram Username Checker No Rate Limits by @glebxdlol")
    print()
    print("[*] Initializing session with fragment.com...")
    session, version, api_url = init_session()
    print(f"[*] API URL: {api_url}\n")

    if usernames:
        usernames = [u.lstrip("@") for u in usernames]
        print(f"[*] Checking {len(usernames)} username(s)...\n")
        results_list = []
        for i, username in enumerate(usernames):
            if i > 0 and args.delay:
                time.sleep(args.delay)
            print(f"[{i + 1}/{len(usernames)}] Checking @{username}...")
            results = check_username(session, api_url, username)
            info = analyze(results)
            results_list.append((username, info))
            print_result(username, info)
            print()

        if len(results_list) > 1:
            print_table(results_list)
            total = len(results_list)
            taken = sum(1 for _, info in results_list if info["exists"])
            free = total - taken
            print(f"\nTotal: {total} | Taken: {taken} | Available: {free}")
    else:
        print("Interactive mode. Enter usernames (Ctrl+C to exit).\n")
        try:
            while True:
                raw = input("> ").strip()
                if not raw:
                    continue
                username = raw.lstrip("@")
                results = check_username(session, api_url, username)
                info = analyze(results)
                print_result(username, info)
                print()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")


if __name__ == "__main__":
    main()
