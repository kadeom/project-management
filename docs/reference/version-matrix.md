# Матрица версий

| Компонент | Версия | Почему |
|---|---|---|
| Python | 3.10–3.14 | пол задают pytest и Pillow, потолок — JPype1 |
| MPXJ | 16.10.0 | XML зависит от writer: FieldGUID, Ltuid, Guid |
| JPype1 | 1.7.1 | нет cp315-wheels, выше 3.14 не ставится |
| Java | 8+ (проверено на 21) | минимум MPXJ; разрядность равна Python |
| python-docx | >= 1.1 | генерация отчёта |
| PyYAML | >= 6 | разбор `project.yaml` |
| MS Project | 2010/2013/2016/365 | `SaveVersion=14` открывается всеми |
| Playwright / TempMail | по необходимости | только `additional-assignment/03-jira`, не CI |

## Правила обновления

1. Обновляйте `pyproject.toml` и `requirements.txt` вместе.
2. Пересоберите `out/` и проверьте diff XML.
3. Запустите `python -m pytest tests -q`.
4. Проверьте отчёт `.docx` визуально.

## Проверка окружения

```bash
python --version
java -version
python -c "import mpxj, jpype; print(mpxj.__version__, jpype.__version__)"
```

## Источники

- https://mpxj.org/
- https://jpype.readthedocs.io/
- https://pypi.org/project/JPype1/
