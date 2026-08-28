# PatientNote — Карта СМП

Настольное приложение (PySide6 + SQLite) для заполнения карт вызова СМП
по шаблону диагноза: жалобы, анамнез, объективно по системам, локальный
статус, оказанная помощь и т.д. В комплекте база из 280 диагнозов с
готовыми шаблонами и кодами МКБ.

## Запуск из исходников

Требуется Python 3.10–3.12.

```bash
pip install PySide6
python main.py
```

## Файлы

| Файл | Назначение |
|---|---|
| `main.py` | Интерфейс приложения (PySide6) |
| `database.py` | Работа с базой данных SQLite |
| `patientnote.db` | База — 280 диагнозов с шаблонами карт вызова |

## Сборка .exe (Windows)

```
pip install pyinstaller
pyinstaller --onedir --windowed --add-data "patientnote.db;." --name PatientNote_SMP main.py
```

Готовый `.exe` появится в `dist/PatientNote_SMP/`. Файл `patientnote.db`
должен лежать рядом с `.exe` в той же папке.
