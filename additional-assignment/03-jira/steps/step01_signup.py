"""Этап 1: регистрация аккаунта Atlassian (Jira free) на реальной почте.

Почта не хранится в репозитории: задайте JIRA_SIGNUP_EMAIL или введите её
при запуске. Для одноразового ящика используйте mail_account.py.
"""

import os

from common import browser, shot

EMAIL_URL = ("https://www.atlassian.com/try/cloud/signup"
             "?bundle=jira-software&edition=free&skipBundles=true")
EMAIL = os.environ.get("JIRA_SIGNUP_EMAIL", "").strip()


def main():
    email = EMAIL or input("Work email: ").strip()
    if not email:
        raise SystemExit("нужен адрес почты: JIRA_SIGNUP_EMAIL")
    pw, ctx = browser()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(EMAIL_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    shot(page, "01_signup_form", "форма регистрации Jira")

    page.get_by_label("Work email").fill(email)
    page.get_by_role("button", name="Sign up").click()
    page.wait_for_timeout(12000)
    shot(page, "02_after_email", "после отправки email")
    print("URL:", page.url[:300])
    print("TEXT:", page.inner_text("body")[:1200])
    # не закрываем браузер — ждём код
    input("Вставьте код и нажмите ENTER... ")


if __name__ == "__main__":
    main()
