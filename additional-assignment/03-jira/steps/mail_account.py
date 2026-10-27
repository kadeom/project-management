"""Создание временного почтового ящика (tempmail.lol) для регистрации в Jira."""
import json
import pathlib
import time

from TempMail import TempMail

OUT = pathlib.Path(__file__).with_name("creds.json")


def main():
    last = None
    for _ in range(6):
        try:
            inb = TempMail().createInbox()
            creds = {
                "address": inb.address,
                "token": inb.token,
                "provider": "tempmail.lol",
            }
            OUT.write_text(json.dumps(creds, indent=2), encoding="utf-8")
            print(json.dumps(creds, indent=2))
            return
        except Exception as e:  # noqa: BLE001
            last = repr(e)
            time.sleep(5)
    raise RuntimeError(f"tempmail: {last}")


if __name__ == "__main__":
    main()
