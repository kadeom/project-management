"""Этап 1: регистрация аккаунта Atlassian (Jira free) на реальной почте."""

from common import browser, shot

EMAIL_URL = ("https://www.atlassian.com/try/cloud/signup"
             "?bundle=jira-software&edition=free&skipBundles=true")
EMAIL = "d.o.koshevoi@gmail.com"


def main():
    pw, ctx = browser()
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(EMAIL_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    shot(page, "01_signup_form", "форма регистрации Jira")

    page.get_by_label("Work email").fill(EMAIL)
    page.get_by_role("button", name="Sign up").click()
    page.wait_for_timeout(12000)
    shot(page, "02_after_email", "после отправки email")
    print("URL:", page.url[:300])
    print("TEXT:", page.inner_text("body")[:1200])
    # не закрываем браузер — ждём код
    input("Вставьте код и нажмите ENTER... ")


if __name__ == "__main__":
    main()
