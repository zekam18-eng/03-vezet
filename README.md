# PatientNote — Карта СМП

Приложение для заполнения карт вызова СМП по шаблону диагноза: жалобы,
анамнез, объективно по системам, локальный статус, оказанная помощь и
т.д. В базе — 280 диагнозов с готовыми шаблонами и кодами МКБ, плюс
15 случаев сердечно-лёгочной реанимации с полным протоколом СЛР.

Два варианта в этом репозитории:

## 1. Desktop-приложение (Windows/Linux/macOS)

`main.py` + `database.py` + `patientnote.db` — PySide6 + SQLite.

```bash
pip install PySide6
python main.py
```

Сборка `.exe`:
```
pip install pyinstaller
python -m PyInstaller --onefile --windowed --add-data "patientnote.db;." --name PatientNote_SMP main.py
```

## 2. Веб-версия / Telegram Mini App

Папка `webapp/` — самостоятельная веб-страница (HTML/CSS/JS, без
бэкенда), вся база из 280+15 диагнозов зашита в `data.json`.
Работает как обычный сайт и как мини-приложение внутри Telegram.

- Просмотр и поиск по диагнозам и кодам МКБ
- Редактирование карты, копирование готового текста
- Сохранение карт в историю (хранится локально в браузере/Telegram)
- Обе вкладки — «Карта СМП» и «Реанимация»

### Публикация на GitHub Pages

1. Settings → Pages → Source: Deploy from a branch → Branch: `main`,
   папка `/webapp`.
2. Через пару минут страница будет доступна по адресу вида
   `https://<юзернейм>.github.io/<репозиторий>/`.

### Подключение как Telegram Mini App

1. Открой `@BotFather` в Telegram → `/newbot` (если бота ещё нет).
2. `/mybots` → выбери бота → `Bot Settings` → `Menu Button` →
   `Configure Menu Button` → вставь ссылку на GitHub Pages из шага выше.
3. Открой бота в Telegram — кнопка меню откроет мини-приложение.

Так же можно подключить как `Web App` кнопку прямо в сообщении бота
(через `/newapp` в BotFather) — если планируется более сложный сценарий
запуска.
