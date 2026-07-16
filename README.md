# ChatList

ChatList — настольное приложение на Python с графическим интерфейсом PyQt6. Позволяет отправлять один промт в несколько нейросетей и сравнивать их ответы.

Документация:
- [PROJECT.md](PROJECT.md) — описание проекта
- [PLAN.md](PLAN.md) — план реализации
- [DATABASE.md](DATABASE.md) — схема базы данных

## Требования

- Python 3.13+
- Windows PowerShell

## Установка

```powershell
cd C:\Work\ChatList_1
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Настройка API-ключей

```powershell
Copy-Item .env.example .env
```

Откройте `.env` и укажите свои ключи:

```env
OPENROUTER_API_KEY=sk-or-v1-...
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
GROQ_API_KEY=gsk_...
```

Файл `.env` не попадает в репозиторий.

## Запуск программы

```powershell
cd C:\Work\ChatList_1
.\.venv\Scripts\Activate.ps1
python main.py
```

После запуска откроется окно ChatList:
1. Введите промт в текстовое поле.
2. Нажмите **«Отправить»** — таблица заполнится тестовыми ответами (режим заглушки).
3. Отметьте нужные строки чекбоксом **«Выбрать»**.
4. Кнопка **«Сохранить»** пока показывает сообщение — полное сохранение в БД будет на этапе 6.

## Структура модулей

| Модуль       | Назначение                        |
|--------------|-----------------------------------|
| `db.py`      | Работа с SQLite                   |
| `models.py`  | Логика моделей и промтов          |
| `network.py` | HTTP-запросы к API нейросетей     |
| `main.py`    | Графический интерфейс PyQt        |

## Проверка базы данных

```powershell
python db.py
```

## Сборка exe (PyInstaller)

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\pyinstaller.exe --onefile --noconsole --name ChatList --collect-all PyQt6 main.py
```

Готовый файл: `C:\Work\ChatList_1\dist\ChatList.exe`
