# Управленческие артефакты проекта

Шаблоны документов, которые дополняют расписание и смету. Они не генерируются
из `project.yaml` автоматически: часть полей — управленческие решения, а не
расчёт. Заполняйте копию шаблона в каталоге своего проекта, не меняя оригинал.

| Шаблон | Когда нужен | Кто заполняет |
|---|---|---|
| [`templates/project-charter.md`](templates/project-charter.md) | инициация | руководитель проекта |
| [`templates/stakeholder-register.md`](templates/stakeholder-register.md) | инициация и планирование | руководитель + заказчик |
| [`templates/wbs-dictionary.md`](templates/wbs-dictionary.md) | после построения СДР | руководитель + команда |
| [`templates/raci-matrix.md`](templates/raci-matrix.md) | планирование ролей | руководитель |
| [`templates/risk-register.md`](templates/risk-register.md) | планирование и контроль | руководитель + команда |
| [`templates/quality-plan.md`](templates/quality-plan.md) | планирование качества | ответственный за качество |
| [`templates/communication-plan.md`](templates/communication-plan.md) | планирование коммуникаций | руководитель |
| [`templates/change-log.md`](templates/change-log.md) | исполнение | руководитель |
| [`templates/status-report.md`](templates/status-report.md) | контроль | руководитель |
| [`templates/closure-report.md`](templates/closure-report.md) | завершение | руководитель + заказчик |

## Готовый пример

[`example-conference-2026.md`](example-conference-2026.md) — заполненный паспорт
проекта CONF-2026: устав, заинтересованные стороны, СДР, RACI, риски,
качество, коммуникации, изменения, статус и завершение. Сборка:

```bash
python build_artifacts.py        # out/project-artifacts.docx
```

## Правила

- Один артефакт — один файл; версия и дата обязательны.
- Числа (сроки, стоимость, трудозатраты) берутся из `out/analysis.md` или
  `out/expected.json`, а не вводятся вручную.
- Имена и контакты — только учебные; реальные персональные данные запрещены.
- Ссылки на стандарты — по ГОСТ Р 7.0.100-2018.
