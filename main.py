#!/usr/bin/env python3
"""atria-key-inject — log into Atria via Google SSO and extract API keys.

Usage:
    export ATRIA_PASSWORD='***'          # your Google password (never logged)
    python main.py --accounts accounts.txt --out keys.json
    python main.py --email you@example.com
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from google_login import GoogleLogin, LoginBlocked, SIGNIN_URL
from atria_keys import create_key, list_existing_keys, KeyError_

PROFILE_BASE = Path(__file__).parent / "profiles"
KEY_NAME_PREFIX = os.environ.get("KEY_NAME_PREFIX", "atria-inject")

# Bulk mode ( --accounts ) is donor-gated. After supporting the project you receive
# an unlock word; set it in the ATRIA_UNLOCK env var to enable multi-account runs.
# Single-account mode ( --email ) is free for everyone.
_UNLOCK_FILE = Path(__file__).parent / ".unlock"
_UNLOCK_SECRET = b"atria-inject-tools::bulk-mode::v1"


def _unlock_hash(word: str) -> str:
    return hmac.new(_UNLOCK_SECRET, word.strip().lower().encode(), hashlib.sha256).hexdigest()


def _expected_unlock_hash() -> str | None:
    """The unlock hash is NOT shipped in the repo — it lives in .unlock (gitignored)
    and only on the maintainer's machine, so the published repo cannot be cracked
    by reading it. Returns None when the file is absent (bulk fully locked)."""
    try:
        return _UNLOCK_FILE.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _bulk_unlocked() -> bool:
    """True when the user has set ATRIA_UNLOCK to the donor unlock word."""
    word = os.environ.get("ATRIA_UNLOCK", "")
    if not word:
        return False
    expected = _expected_unlock_hash()
    if not expected:
        return False
    return hmac.compare_digest(_unlock_hash(word), expected)


def _unlock_hint() -> str:
    return (
        "\nBulk mode (--accounts) memerlukan kata pembuka.\n"
        "Dukung proyek ini di https://saweria.co/pandualdi lalu set:\n"
        "  set ATRIA_UNLOCK=<kata pembuka>\n"
        "Mode satuan (--email ADDR) gratis untuk semua."
    )


def read_accounts(path: Path) -> list[str]:
    """accounts.txt: one email per line; blank lines and # comments ignored."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "@" in line:
            out.append(line)
    return out


def is_logged_in(page) -> bool:
    """If the profile is already authenticated, /console/keys loads the console."""
    try:
        page.goto("https://api.atria-asi.ai/console/keys", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        url = page.url
        # Not bounced back to the sign-in page → authenticated
        return "/sign-in" not in url and "accounts.google.com" not in url
    except Exception:
        return False


def run_account(email: str, password: str, out_path: Path, headed: bool, create: bool) -> dict:
    profile_dir = PROFILE_BASE / email.replace("@", "_at_")
    profile_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    result = {"email": email, "ok": False, "error": None, "key": None,
              "key_name": None, "created_at": stamp, "profile": str(profile_dir)}

    # One playwright instance per account, always torn down — a leaked context
    # from account N breaks account N+1 with TargetClosedError.
    pw = sync_playwright().start()
    try:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not headed,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1280, "height": 900},
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            # Fast path: persistent profile still holds a Google session.
            if is_logged_in(page):
                result["login"] = "reused"
            else:
                gl = GoogleLogin(page, email, password)
                gl.start()
                gl.login()
                result["login"] = "google"

            if not is_logged_in(page):
                raise RuntimeError("landed on Atria but /console/keys still redirects to sign-in")

            existing = list_existing_keys(page)
            if existing and not create:
                result["key"] = existing[0]
                result["key_name"] = "(existing)"
                result["ok"] = True
                result["note"] = f"{len(existing)} existing key(s); pass --create to make a new one"
            else:
                name = f"{KEY_NAME_PREFIX} {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                key = create_key(page, name)
                result["key"] = key
                result["key_name"] = name
                result["ok"] = True

        except LoginBlocked as e:
            result["error"] = f"login blocked: {e}"
        except PlaywrightTimeout as e:
            result["error"] = f"timeout: {e}"
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}"
        finally:
            # Close context even on exceptions, or the next account's launch
            # races the old browser process.
            try:
                ctx.close()
            except Exception:
                pass
    finally:
        pw.stop()

    _append(out_path, result)
    return result


def _append(out_path: Path, result: dict) -> None:
    """Append one result; create the file with a JSON array shape."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if out_path.exists():
        try:
            rows = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            rows = []
    rows.append(result)
    out_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--accounts", type=Path, help="file with one email per line")
    ap.add_argument("--email", help="single account")
    ap.add_argument("--out", type=Path, default=Path("keys.json"))
    ap.add_argument("--headless", action="store_true", help="run without a visible window")
    ap.add_argument("--create", action="store_true",
                    help="always create a new key even if one exists")
    args = ap.parse_args()

    emails: list[str] = []
    if args.accounts:
        if not _bulk_unlocked():
            print("Bulk mode terkunci." + _unlock_hint(), file=sys.stderr)
            return 3
        emails = read_accounts(args.accounts)
    if args.email:
        emails.append(args.email)
    if not emails:
        ap.error("no accounts: pass --accounts FILE or --email ADDR")

    password = os.environ.get("ATRIA_PASSWORD", "")
    if not password:
        print("ATRIA_PASSWORD not set — set it first:\n  export ATRIA_PASSWORD='***'",
              file=sys.stderr)
        return 2

    print(f"accounts: {len(emails)}")
    failures = 0
    for email in emails:
        print(f"\n[{'-' * 4}] {email}")
        r = run_account(email, password, args.out, headed=not args.headless, create=args.create)
        if r["ok"]:
            print(f"  OK  key={r['key'][:8]}...{r['key'][-4:] if r['key'] else ''} "
                  f"login={r.get('login')} name={r['key_name']}")
        else:
            failures += 1
            print(f"  FAIL {r['error']}")

    print(f"\ndone. ok={len(emails) - failures} fail={failures} -> {args.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
