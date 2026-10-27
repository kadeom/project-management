# Changelog

Все заметные изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
проект следует [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Дополнительное задание: варианты 12 (PAM) и 10 (DLP+SIEM),
  `build_infosec.py`, `src/pm/report_infosec.py`, `src/pm/currency.py`.
- XML и `.mpp` для обоих вариантов: `out/infosec_v12_full.*`, `out/infosec_v10_full.*`.
- Справочники `docs/reference/infosec/` и руководство
  `docs/guides/additional-assignment.md`.
- Эксперимент Jira в `additional-assignment/03-jira/`.
- Корневые документы: `AGENTS.md`, `ARCHITECTURE.md`, `BACKLOG.md`,
  `ROADMAP.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`.
- `docs/`: архитектура, ADR, руководства, справочники, реестр задач.
- `schemas/project.schema.json` и `examples/` с форматом `project.yaml`.
- `scripts/check.sh` и проверка относительных Markdown-ссылок.
- `.editorconfig`, `.gitattributes`, шаблон коммита и каркас GitHub Actions.

### Changed

- Пакет перенесён из `pm/` в `src/pm/`.
- `build.py`, тесты и Windows-автоматизация добавляют в `sys.path` каталог `src/`.
- `scripts/xml_to_mpp.py` берёт имена файлов из `src/pm/paths.py`.
- Чек-лист перенесён в `docs/guides/checklist.md`.
- Ссылки на отсутствующие `docs/product/reference/*` заменены на
  `docs/reference/*`.
- Короткие ID задач (`T07`, `T09`, …) приведены к формату `T-007`, `T-009`, …

### Security

- Адрес почты для Jira вынесен в `JIRA_SIGNUP_EMAIL`; токены и профиль браузера
  исключены через `.gitignore`.

### Fixed

- `pyproject.toml` описывает src-layout (`package-dir`, `pythonpath`).
- README больше не ссылается на несуществующий CI и старые пути пакета.

## Источники

- https://keepachangelog.com/en/1.1.0/
- https://semver.org/
