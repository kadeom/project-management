# Политика безопасности

## Поддерживаемые версии

| Версия | Поддержка |
|---|---|
| 0.1.x | да |

## Как сообщить об уязвимости

Не создавайте публичный issue. Используйте приватный канал GitHub:
вкладка **Security and quality** → **Report a vulnerability**.

Что приложить: версию, шаги воспроизведения, влияние, при наличии — PoC.
Срок первого ответа — 7 дней.

## Что входит в область

- выполнение кода из `project.yaml` и `out/`;
- обработка XML и `.docx`;
- зависимости Python и Java;
- GitHub Actions;
- утечка локальных путей и данных в артефактах.

## Что не считается уязвимостью

- дефекты MS Project;
- поведение сторонних библиотек без влияния на репозиторий;
- ошибки в учебных данных;
- отсутствие функции, которая не заявлена.

## Меры

- Зависимости закреплены точно, обновление — через PR.
- Сборка не использует сеть.
- Внешний XML не парсится.
- Секретов в репозитории нет.
- Подробности — [`docs/reference/security-notes.md`](docs/reference/security-notes.md).

## Источники

- https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability
- https://openssf.org/
