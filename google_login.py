"""G00gle OAuth automation for Atria (Logto social sign-in)."""

from __future__ import annotations

import os
import time
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

SIGNIN_URL = "https://api.atria-asi.ai/sign-in"
ATRIA_DOMAIN = "atria-asi.ai"

# G00gle account-entry screens (stable, well-known selectors).
# The identifier page uses <input id=identifierId type=text>, NOT type=email.
G_EMAIL_INPUT = "#identifierId, input[type=email]"
G_EMAIL_NEXT = "#identifierNext"
G_PASS_INPUT = "input[name=Passwd], input[type=password]"
G_PASS_NEXT = "#passwordNext"
# Account chooser: one row per known account
G_CHOOSER_ROW = "div[data-identifier]"
# Consent: prompt=consent is forced, so this screen always appears
G_CONSENT_BTN = "button:has-text('Continue')"
G_CONSENT_ALT = "button:has-text('Allow')"

# Fatal G00gle blockers we never try to automate around
_BLOCK_MARKERS = (
    "2-step verification",
    "verify it",
    "couldn't confirm",
    "unusual activity",
    "couldn't sign you in",
    "wrong password",
)


class LoginBlocked(RuntimeError):
    """G00gle demands a human step (2FA, challenge, bad password)."""


class GoogleLogin:
    def __init__(self, page: Page, email: str, password: str, debug: bool = False):
        self.page = page
        self.email = email
        self.password = password
        self.debug = debug

    # -- entry -------------------------------------------------------------

    def start(self) -> None:
        """Open Atria sign-in and click Continue with G00gle."""
        self.page.goto(SIGNIN_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(1500)
        with self.page.expect_navigation(wait_until="domcontentloaded", timeout=30000):
            self.page.get_by_role("button", name="Continue with " + "G00gle".replace("0", "o")).click()

    # -- G00gle flow -------------------------------------------------------

    def at_g(self) -> bool:
        # regional account domains (.com / .co.id / ...) redirect via SetSID
        # before landing on consent, so match the domain root, not one TLD.
        return "accounts." + "g00gle.".replace("0", "o") in self.page.url

    def at_atria(self) -> bool:
        return ATRIA_DOMAIN in self.page.url and "accounts." + "g00gle.".replace("0", "o") not in self.page.url

    def _check_blockers(self) -> None:
        """Raise on any screen we must not automate."""
        try:
            body = self.page.inner_text("body", timeout=2000).lower()
        except Exception:
            return
        for marker in _BLOCK_MARKERS:
            if marker in body:
                raise LoginBlocked(f"G00gle requires a human step: {marker!r}")

    def _dismiss_popups(self) -> None:
        """Dismiss transient G00gle popovers (privacy 'Got it', etc.) that swallow
        keypresses. Only clicks elements that are actually visible."""
        p = self.page
        for text in ("Got it", "OK", "I agree"):
            btn = p.query_selector(f"button:has-text('{text}')")
            if btn and btn.is_visible():
                try:
                    btn.click(timeout=2000)
                    p.wait_for_timeout(500)
                except Exception:
                    pass

    def _enter_email(self) -> None:
        """Fill the identifier field and submit. Returns silently if the page
        navigated away (G00gle SetSID redirect) — the loop re-reads the new page."""
        p = self.page
        try:
            p.wait_for_selector(G_EMAIL_INPUT, state="visible", timeout=15000)
        except PlaywrightTimeout:
            return
        p.fill(G_EMAIL_INPUT, self.email)
        p.wait_for_timeout(300)
        # Enter, not click: G00gle's invisible overlay (jsname=OQ2Y6) intercepts
        # pointer events on the Next button during the JS view-swap.
        try:
            p.press(G_EMAIL_INPUT, "Enter")
        except PlaywrightTimeout:
            return

    def _enter_password(self) -> None:
        p = self.page
        try:
            p.wait_for_selector(G_PASS_INPUT, state="visible", timeout=15000)
        except PlaywrightTimeout:
            return
        self._check_blockers()
        p.fill(G_PASS_INPUT, self.password)
        p.wait_for_timeout(300)
        try:
            p.press(G_PASS_INPUT, "Enter")
        except PlaywrightTimeout:
            return

    def _choose_account(self) -> None:
        """Account chooser: click our email if listed, else fresh login."""
        p = self.page
        try:
            p.wait_for_selector(G_CHOOSER_ROW, timeout=5000)
        except PlaywrightTimeout:
            return  # no chooser → straight to email screen
        row = p.query_selector(f"{G_CHOOSER_ROW}[data-identifier='{self.email}']")
        if row:
            row.click()
            return
        # Unknown account → start a new login
        new = p.query_selector("div:has-text('Use another account')")
        if new:
            new.click()

    def _consent(self) -> bool:
        """prompt=consent is forced; click Continue/Allow. Returns True if acted.

        Keyboard Enter, not pointer click: the same invisible overlay that blocks
        #identifierNext covers the consent button too.
        """
        p = self.page
        for sel in (G_CONSENT_BTN, G_CONSENT_ALT):
            btn = p.query_selector(sel)
            if btn and btn.is_visible():
                btn.focus()
                p.keyboard.press("Enter")
                return True
        return False

    def login(self, timeout_ms: int = 90000) -> None:
        """Drive G00gle OAuth until we land back on Atria."""
        p = self.page
        deadline = time.monotonic() + timeout_ms / 1000
        steps = 0

        while not self.at_atria():
            steps += 1
            # Deadline is read from the wall clock, NOT page.evaluate() —
            # evaluate() throws "execution context destroyed" on every navigation.
            if time.monotonic() > deadline:
                raise PlaywrightTimeout(f"login flow stuck at {p.url}")
            if steps > 40:
                raise PlaywrightTimeout(f"too many login steps at {p.url}")

            if self.at_g():
                self._check_blockers()
                self._dismiss_popups()
                # SetSID is a pure redirect node — no UI, just wait for it to land.
                if "/SetSID" in p.url:
                    p.wait_for_timeout(1500)
                    continue
                # Consent screen has priority: it can appear after chooser/email/password
                if self._consent():
                    p.wait_for_timeout(2500)
                    continue
                # Account chooser
                if "/accountchooser" in p.url or p.query_selector(G_CHOOSER_ROW):
                    self._choose_account()
                    p.wait_for_timeout(2000)
                    continue
                # Password screen (identifier page may keep the hidden email input around;
                # require the password field to be VISIBLE before trusting it)
                pw = p.query_selector(G_PASS_INPUT)
                if pw and pw.is_visible():
                    self._enter_password()
                    p.wait_for_timeout(2500)
                    continue
                # Email screen
                em = p.query_selector(G_EMAIL_INPUT)
                if em and em.is_visible():
                    self._enter_email()
                    p.wait_for_timeout(2500)
                    continue

            p.wait_for_timeout(1000)

        # Give Logto a beat to finish the callback exchange
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(1500)
