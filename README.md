# ChatList

ChatList — настольное приложение на Python с графическим интерфейсом PyQt6. Позволяет отправлять один промт в несколько нейросетей через OpenRouter и сравнивать их ответы.

Документация:
- [PROJECT.md](PROJECT.md) — описание проекта
- [PLAN.md](PLAN.md) — план реализации
- [DATABASE.md](DATABASE.md) — схема базы данных

## Требования

- Python 3.13+
- Windows PowerShell
- API-ключ [OpenRouter](https://openrouter.ai/)

## Установка

```powershell
cd C:\Work\ChatList_1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Настройка

```powershell
Copy-Item .env.example .env
```

Откройте `.env` и укажите значения:

```env
OPENROUTER_API_KEY=ваш_ключ_openrouter
OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

Файл `.env` не попадает в репозиторий.

## Запуск программы

```powershell
cd C:\Work\ChatList_1
.\.venv\Scripts\Activate.ps1
python main.py
```

## Использование

1. Введите промт в текстовое поле или выберите сохранённый из выпадающего списка.
2. Нажмите **«Отправить»** — запрос уйдёт во все активные модели через OpenRouter.
3. Отметьте нужные ответы чекбоксом **«Выбрать»**.
4. Нажмите **«Сохранить выбранные»** — отмеченные ответы попадут в базу данных.
5. Кнопка **«Очистить»** очищает поле промта и временную таблицу.

### Меню

| Пункт | Назначение |
|-------|------------|
| **Промты** | Просмотр, поиск и удаление сохранённых промтов |
| **Модели** | Управление моделями OpenRouter (добавление, редактирование, вкл/выкл) |
| **Результаты** | Просмотр сохранённых ответов, поиск, экспорт в Markdown/JSON |
| **Настройки** | Таймаут запросов, путь к БД, теги по умолчанию, логирование |

## Структура модулей

| Модуль       | Назначение                        |
|--------------|-----------------------------------|
| `db.py`      | Работа с SQLite                   |
| `models.py`  | Логика моделей, промтов, настроек |
| `network.py` | HTTP-запросы к OpenRouter         |
| `dialogs.py` | Диалоги управления данными        |
| `main.py`    | Графический интерфейс PyQt        |

## Проверка базы данных

```powershell
python db.py
```

## Сборка exe (PyInstaller)

```powershell
.\venv\Scripts\python.exe -m pip install pyinstaller
.\venv\Scripts\python.exe build.py
```

Готовый файл: `dist\ChatList.exe`

## Сборка установщика (Inno Setup)

```powershell
.\venv\Scripts\python.exe -m pip install pyinstaller
.\venv\Scripts\python.exe build_installer.py
```

Скрипт собирает `dist\ChatList.exe`, затем создаёт установщик в папке `install\`.
Имя установщика берётся из `version.py`, например: `install\ChatList-1.0.0-Setup.exe`.

Требуется [Inno Setup 6](https://jrsoftware.org/isinfo.php).

## Файлы данных

| Файл | Описание |
|------|----------|
| `chatlist.db` | База данных SQLite |
| `chatlist.log` | Лог HTTP-запросов (если включён в настройках) |
| `.env` | API-ключи (не в репозитории) |
