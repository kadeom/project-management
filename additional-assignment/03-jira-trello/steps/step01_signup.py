"""Этап 1: регистрация аккаунта Atlassian (Jira free) на временной почте."""
import json

from common import browser, creds, close, shot, inbox

EMAIL_URL = ("https://www.atlassian.com/try/cloud/signup"
             "?bundle=jira-software&edition=free&skipBundles=true")


def main():
    c = creds()
    pw, ctx = browser()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(EMAIL_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    shot(page, "dbg_signup_form", "форма регистрации Jira")

    page.get_by_label("Work email").fill(c["address"])
    page.get_by_role("button", name="Sign up").click()
    page.wait_for_timeout(10000)
    shot(page, "dbg_after_email", "после отправки email")
    print("URL:", page.url[:200])
    print("TEXT:", page.inner_text("body")[:800])

    try:
        msg = inbox(c, wait=120)
        print("MAIL:", json.dumps(msg, ensure_ascii=False, indent=2)[:3000])
    except Exception as e:  # noqa: BLE001
        print("mail err:", e)

    close(pw, ctx)


if __name__ == "__main__":
    main()
