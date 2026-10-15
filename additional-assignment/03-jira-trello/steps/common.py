"""Общие помощники: постоянный профиль Chromium и работа с временной почтой."""
import json
import pathlib
import time

import requests
from playwright.sync_api import sync_playwright

BASE = pathlib.Path(__file__).resolve().parent
PROF = BASE / "profile"
SHOTS = BASE.parent / "shots"
CREDS = BASE / "creds.json"
MAIL = "https://api.tempmail.lol"

VIEW = {"width": 1440, "height": 900}


def creds():
    return json.loads(CREDS.read_text(encoding="utf-8"))


def browser():
    PROF.mkdir(exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        str(PROF),
        channel="chrome",
        headless=False,
        viewport=VIEW,
        locale="en-US",
    )
    ctx.set_default_timeout(45000)
    return pw, ctx


def shot(page, name, note=""):
    p = SHOTS / f"{name}.png"
    page.screenshot(path=str(p))
    print(f"[shot] {p.name} {note} :: {page.url}")
    return p


def mail_get(c, tries=3):
    last = None
    from TempMail import TempMail
    tmp = TempMail()
    for _ in range(tries):
        try:
            return tmp.getEmails(c["token"])
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(3)
    raise RuntimeError(f"mail get: {last}")


def inbox(c, wait=300):
    """Ждём первое письмо и возвращаем его."""
    t0 = time.time()
    while time.time() - t0 < wait:
        try:
            emails = mail_get(c, tries=1) or []
        except Exception:  # noqa: BLE001
            emails = []
        if emails:
            return emails[0]
        time.sleep(6)
    raise TimeoutError("письмо не пришло")


def find_link(text, *needles):
    import re
    for u in re.findall(r"https?://[^\s\"'<>]+", text or ""):
        if all(n in u for n in needles):
            return u.rstrip(").,")
    return None


def close(pw, ctx):
    try:
        ctx.close()
    finally:
        pw.stop()
