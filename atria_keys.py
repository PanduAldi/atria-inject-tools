"""Atria console: navigate to /console/keys and extract API keys."""

from __future__ import annotations

import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

KEYS_URL = "https://api.atria-asi.ai/console/keys"
CREATE_BTN = "button[aria-haspopup=dialog]:has-text('Create key')"
DIALOG = "dialog.key-create-dialog"
DIALOG_NAME_SUFFIX = "-name"
DIALOG_SUBMIT = "button.key-dialog-primary"
DIALOG_CLOSE = "button.key-dialog-close"

# The created key is shown once. Try the most common shapes in order.
KEY_VALUE_SELECTORS = (
    "dialog.key-create-dialog kbd",
    "dialog.key-create-dialog code",
    "dialog.key-create-dialog input[readonly]",
    "dialog.key-create-dialog [data-key-value]",
    "dialog.key-create-dialog input[type=text]",
)

# Atria keys look like a long opaque token; fall back to "any long hex-ish blob".
_KEY_RE = re.compile(r"[A-Za-z0-9_\-]{32,}")


class KeyError_(RuntimeError):
    pass


def list_existing_keys(page: Page) -> list[str]:
    """Return key names/values already on the page (best effort)."""
    page.goto(KEYS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    values = []
    for sel in ("main kbd", "main code", "main input[readonly]"):
        for el in page.query_selector_all(sel):
            t = (el.inner_text() or "").strip()
            if t:
                values.append(t)
    return values


def extract_created_key(page: Page) -> str:
    """Pull the freshly created key out of the still-open dialog."""
    page.wait_for_selector(DIALOG, state="visible", timeout=20000)
    page.wait_for_timeout(800)

    for sel in KEY_VALUE_SELECTORS:
        el = page.query_selector(sel)
        if el:
            t = (el.inner_text() or "").strip()
            if not t:
                t = (el.get_attribute("value") or "").strip()
            if t and _KEY_RE.search(t):
                return t

    # Fall back: any long opaque string inside the dialog
    body = page.inner_text(DIALOG)
    m = _KEY_RE.search(body)
    if m:
        return m.group(0)

    raise KeyError_("created key not found in dialog; dump the dialog HTML to see its shape")


def create_key(page: Page, name: str) -> str:
    """Open the Create key dialog, fill the name, submit, return the new key."""
    page.goto(KEYS_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    if not page.query_selector(CREATE_BTN):
        raise KeyError_("no '+ Create key' button on /console/keys")

    page.click(CREATE_BTN)
    dialog = page.wait_for_selector(DIALOG, state="visible", timeout=15000)
    dialog_id = dialog.get_attribute("id") or ""

    name_input = page.wait_for_selector(f"#{dialog_id}{DIALOG_NAME_SUFFIX}", timeout=10000)
    name_input.fill(name)
    page.wait_for_timeout(400)

    page.click(DIALOG_SUBMIT)

    # The dialog re-renders to show the key. Wait for the form to settle.
    try:
        page.wait_for_function(
            """() => {
                const d = document.querySelector('dialog.key-create-dialog');
                if (!d) return false;
                const f = d.querySelector('form');
                return !f || !f.getAttribute('aria-busy') || f.getAttribute('aria-busy') === 'false';
            }""",
            timeout=15000,
        )
    except PlaywrightTimeout:
        pass

    key = extract_created_key(page)

    # Close the dialog so the next account starts clean.
    close = page.query_selector(DIALOG_CLOSE)
    if close:
        close.click()
        page.wait_for_timeout(400)
    return key
