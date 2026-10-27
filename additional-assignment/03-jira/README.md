# Jira: регистрация и скриншоты

Эксперимент по регистрации в Jira через реальный браузер. Не входит в
`build.py`, `build_infosec.py` и CI: нужны Playwright, Chrome и внешний сервис.

## Зависимости

```bash
pip install playwright
python -m playwright install chrome
pip install TempMail
```

`TempMail` — клиент временной почты. Для постоянной почты используйте переменную
`JIRA_SIGNUP_EMAIL`; адрес в коде не хранится.

## Порядок

```bash
cd additional-assignment/03-jira/steps
python mail_account.py          # создать временный ящик → creds.json
python step01_signup.py         # открыть форму Jira и ввести почту
```

`step01_signup.py` ждёт код подтверждения: `input()` не закрывает браузер.

## Что не коммитится

- `steps/creds.json` — адрес и токен временного ящика;
- `steps/profile/` — профиль Chromium с сессиями.

Эти пути перечислены в `.gitignore`. Не добавляйте реальные адреса, пароли и
токены в код, скриншоты и отчёты.

## Скриншоты

- `shots/01_signup_form.png` — форма регистрации;
- `shots/02_after_email.png` — экран после отправки;
- `shots/dbg_*.png` — отладочные кадры.

## Источники

- https://playwright.dev/python/
- https://www.atlassian.com/software/jira
