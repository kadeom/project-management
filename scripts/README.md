# Скрипты

| Файл | Назначение | Платформа |
|---|---|---|
| [`xml_to_mpp.py`](xml_to_mpp.py) | `out/*.xml` → `out/*.mpp` через COM | Windows + MS Project |
| [`fx_rate.py`](fx_rate.py) | блок `fx` для валютной сметы (НБКР → ЦБ РФ → резерв) | сеть, вручную |
| [`check.sh`](check.sh) | все проверки | Linux/macOS/WSL |
| [`checks/docs-paths.sh`](checks/docs-paths.sh) | относительные Markdown-ссылки | Linux/macOS/WSL |
| [`checks/python.sh`](checks/python.sh) | `ruff` и `pytest` | Linux/macOS/WSL |

## Проверки

```bash
./scripts/check.sh          # всё
./scripts/check.sh docs     # только ссылки
```

`check.sh` обходит `checks/*.sh` по алфавиту. Файлы с префиксом `_` пропускаются:
это шаблоны.

## Windows

`xml_to_mpp.py` импортирует `win32com` и запускается только на Windows с
установленным MS Project. На Linux он не входит в тесты и CI.
