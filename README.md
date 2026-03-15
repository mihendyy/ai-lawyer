# ИИшка — бот для разбора договоров

Telegram-бот, который по загруженному договору (.doc/.docx) строит схему бизнес-процесса и даёт текстовые рекомендации с рисками.

## Что умеет

- Команда `/start` и кнопка «Загрузить договор»
- Приём только файлов **.doc** и **.docx**
- Анализ текста через AiTunnel (OpenAI-совместимый API)
- Выдача:
  - **Схема в стиле BPMN** (приоритет): дорожки по ответственным (Заказчик, Исполнитель и т.д.), шаги и связи в HTML
  - **Fallback**: если модель не вернула валидный JSON — схема Mermaid в HTML и, при установленном mermaido, PNG
  - Текст **рекомендаций и рисков**

## Установка и запуск

### 1. Окружение

```bash
cd iishka
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Переменные окружения

Скопируйте пример и заполните:

```bash
cp .env.example .env
```

В `.env` укажите:

- `TELEGRAM_BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
- `OPENAI_API_KEY` — ключ AiTunnel (например `sk-aitunnel-...`)
- `OPENAI_BASE_URL` — `https://api.aitunnel.ru/v1/`
- `AI_MODEL` — модель, например `gpt-4o-mini` или `gpt-4o`

### 3. Картинка схемы BPMN (опционально)

Чтобы бот дополнительно присылал изображение BPMN-схемы (PNG) вместе с HTML-файлом, установите Playwright и браузер:

```bash
playwright install chromium
```

Без этого будет отправляться только HTML-файл (схему по-прежнему можно открыть в браузере).

### 4. Запуск бота

```bash
python bot.py
```

Дальше: откройте бота в Telegram, `/start`, затем загрузите договор через кнопку или отправку файла.

## Структура проекта

| Файл | Назначение |
|------|------------|
| `bot.py` | Точка входа, Telegram-обработчики |
| `config.py` | Загрузка настроек из `.env` |
| `docx_reader.py` | Извлечение текста из .docx |
| `prompts.py` | Промпты: JSON (BPMN) + рекомендации, fallback Mermaid |
| `ai.py` | Запрос к AiTunnel, разбор ответа (JSON/Mermaid + рекомендации) |
| `bpmn_schema.py` | Валидация структуры JSON (lanes, steps, connections) |
| `bpmn_render.py` | Рендер JSON в HTML со swimlanes и стрелками |
| `mermaid_render.py` | Рендер Mermaid → PNG (mermaido) и HTML |

## Формат BPMN (JSON)

Модель возвращает структуру: **lanes** (дорожки по ролям), **steps** (шаги с типом start/task/decision/end), **connections** (связи from→to, опционально label). Рендер — фиксированный HTML/JS: одна и та же разметка и скрипты, данные подставляются из JSON. Так схема стабильна, а логику отрисовки можно дорабатывать в одном месте.

## Промпт и доработки

Формат ответа модели задан в `prompts.py`: блоки `---JSON---` и `---РЕКОМЕНДАЦИИ---`. Схему JSON можно уточнять в промпте; визуал дорожек и шагов — в `bpmn_render.py`.

## Документация AiTunnel

- [Документация](https://docs.aitunnel.ru/)
- [Python + OpenAI SDK](https://docs.aitunnel.ru/guides/python-openai-sdk)

