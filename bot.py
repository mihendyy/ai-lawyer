"""
Telegram-бот «ИИшка»: приём .doc/.docx → BPMN-схема процесса по договору.
Соответствие ТЗ: первый результат — всегда BPMN; меню из 5 кнопок.
"""
import uuid
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import DATA_DIR, TELEGRAM_BOT_TOKEN
from docx_reader import extract_text
from ai import (
    analyze_contract,
    analyze_contract_mermaid_fallback,
    get_contract_brief,
    get_contract_risks,
    update_bpmn_from_correction,
)
from mermaid_render import render_mermaid
from bpmn_render import render_bpmn_html, render_bpmn_to_png

MAX_FILE_SIZE_MB = 15
ALLOWED_EXTENSIONS = (".doc", ".docx")

# Ключи в context.user_data
USER_CONTRACT_TEXT = "contract_text"
USER_BPMN_DATA = "bpmn_data"
USER_AWAITING_CORRECTION = "awaiting_correction"


def _menu_buttons() -> InlineKeyboardMarkup:
    """Меню из 5 кнопок: BPMN, Кратко, Риски, Уточнить, Новый договор."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1️⃣ Показать BPMN", callback_data="show_bpmn")],
        [InlineKeyboardButton("2️⃣ Кратко о договоре", callback_data="brief")],
        [InlineKeyboardButton("3️⃣ Ключевые риски", callback_data="risks")],
        [InlineKeyboardButton("4️⃣ Уточнить / внести правку", callback_data="clarify_edit")],
        [InlineKeyboardButton("5️⃣ Загрузить новый договор", callback_data="new_contract")],
    ])


async def _send_bpmn_and_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    bpmn_data: dict,
    caption: str = "BPMN-схема процесса по договору. Откройте в браузере.",
) -> None:
    """Рендерит BPMN в HTML, по возможности — в PNG; отправляет изображение (если есть), файл и меню."""
    user_id = update.effective_user.id if update.effective_user else 0
    work_dir = DATA_DIR / str(user_id)
    work_dir.mkdir(parents=True, exist_ok=True)
    html_path = work_dir / "diagram.html"
    png_path = work_dir / "diagram.png"
    render_bpmn_html(bpmn_data, html_path)
    msg = update.callback_query.message if update.callback_query else update.message
    # Дополнительно: скриншот схемы в PNG (если установлен Playwright)
    png_ok = await render_bpmn_to_png(html_path, png_path)
    if png_ok and png_path.is_file():
        with open(png_path, "rb") as f:
            await msg.reply_photo(photo=f, caption="Схема процесса (изображение).")
    await msg.reply_document(
        document=html_path,
        filename="diagram.html",
        caption=caption,
        reply_markup=_menu_buttons(),
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и просьба загрузить .doc (без выбора режима)."""
    await update.message.reply_text(
        "Привет! Загрузите файл договора в формате .doc или .docx — "
        "я построю BPMN-схему процесса по договору."
    )


def _is_allowed_document(filename: str) -> bool:
    return filename and any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приём .doc/.docx → «Файл получен, анализирую договор» → BPMN → меню."""
    if context.user_data.get(USER_AWAITING_CORRECTION):
        await update.message.reply_text(
            "Сейчас ожидаю текст правки. Напишите, что изменить в процессе, или нажмите «Загрузить новый договор»."
        )
        return

    doc = update.message.document
    if not doc or not doc.file_name:
        await update.message.reply_text("Отправьте, пожалуйста, файл документа.")
        return
    if not _is_allowed_document(doc.file_name):
        await update.message.reply_text(
            "Поддерживаются только форматы .doc и .docx. Загрузите файл в этом формате."
        )
        return
    if doc.file_size and doc.file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        await update.message.reply_text(f"Размер файла не должен превышать {MAX_FILE_SIZE_MB} МБ.")
        return

    # Шаг 2 по ТЗ: сразу сообщение «файл получен, анализирую договор»
    status_msg = await update.message.reply_text("Файл получен, анализирую договор.")

    try:
        file = await context.bot.get_file(doc.file_id)
        work_dir = DATA_DIR / str(uuid.uuid4())
        work_dir.mkdir(parents=True, exist_ok=True)
        docx_path = work_dir / (doc.file_name or "contract.docx")
        await file.download_to_drive(docx_path)

        contract_text = extract_text(docx_path)
        if not contract_text.strip():
            await status_msg.edit_text("В файле не удалось извлечь текст. Проверьте формат (.docx).")
            return

        # Генерация BPMN (первый результат всегда BPMN)
        bpmn_data, _, mermaid_fallback = analyze_contract(contract_text)

        if not bpmn_data and mermaid_fallback and mermaid_fallback.strip():
            await status_msg.edit_text("Строю схему процесса…")
            mermaid_code = analyze_contract_mermaid_fallback(contract_text)
            if mermaid_code.strip():
                png_path, html_path = render_mermaid(mermaid_code, work_dir, base_name="diagram")
                # Fallback: отправляем Mermaid как схему процесса и сохраняем только contract_text
                # (кнопка «Уточнить» для Mermaid не перегенерирует BPMN — можно оставить только текст)
                context.user_data[USER_CONTRACT_TEXT] = contract_text
                context.user_data[USER_BPMN_DATA] = None  # нет BPMN JSON
                await status_msg.delete()
                await update.message.reply_document(
                    document=html_path,
                    filename="diagram.html",
                    caption="Схема процесса. Откройте в браузере.",
                    reply_markup=_menu_buttons(),
                )
                return
            await status_msg.edit_text("Не удалось построить схему. Попробуйте загрузить договор снова.")
            return

        if not bpmn_data:
            await status_msg.edit_text("Не удалось построить BPMN по договору. Попробуйте загрузить файл снова.")
            return

        context.user_data[USER_CONTRACT_TEXT] = contract_text
        context.user_data[USER_BPMN_DATA] = bpmn_data
        context.user_data[USER_AWAITING_CORRECTION] = False

        await status_msg.delete()
        await _send_bpmn_and_menu(update, context, bpmn_data)

    except ValueError as e:
        await status_msg.edit_text(f"Ошибка настроек: {e}")
    except Exception as e:
        await status_msg.edit_text(f"Произошла ошибка: {e}")


async def button_show_bpmn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """1️⃣ Показать BPMN — повторно отправить текущую BPMN и то же меню."""
    query = update.callback_query
    await query.answer()
    bpmn_data = context.user_data.get(USER_BPMN_DATA)
    if not bpmn_data:
        await query.edit_message_text(
            "Сейчас нет сохранённой BPMN. Загрузите договор, чтобы построить схему.",
            reply_markup=_menu_buttons(),
        )
        return
    await _send_bpmn_and_menu(update, context, bpmn_data, caption="BPMN-схема (повторно).")


async def button_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """2️⃣ Кратко о договоре — о чём, стороны, логика, основные блоки."""
    query = update.callback_query
    await query.answer()
    contract_text = context.user_data.get(USER_CONTRACT_TEXT, "")
    if not contract_text.strip():
        await query.edit_message_text(
            "Сначала загрузите договор, чтобы получить краткое описание.",
            reply_markup=_menu_buttons(),
        )
        return
    status_msg = await query.message.reply_text("Формирую краткое описание договора…")
    try:
        text = get_contract_brief(contract_text)
        if not text:
            await status_msg.edit_text("Не удалось сформировать описание.", reply_markup=_menu_buttons())
            return
        if len(text) > 4000:
            text = text[:3997] + "..."
        await status_msg.edit_text("Кратко о договоре:\n\n" + text, reply_markup=_menu_buttons())
    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}", reply_markup=_menu_buttons())


async def button_risks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """3️⃣ Ключевые риски — название, объяснение, возможное улучшение."""
    query = update.callback_query
    await query.answer()
    contract_text = context.user_data.get(USER_CONTRACT_TEXT, "")
    if not contract_text.strip():
        await query.edit_message_text(
            "Сначала загрузите договор, чтобы получить анализ рисков.",
            reply_markup=_menu_buttons(),
        )
        return
    status_msg = await query.message.reply_text("Анализирую риски по договору…")
    try:
        text = get_contract_risks(contract_text)
        if not text:
            await status_msg.edit_text("Не удалось выделить риски.", reply_markup=_menu_buttons())
            return
        if len(text) > 4000:
            text = text[:3997] + "..."
        await status_msg.edit_text("Ключевые риски:\n\n" + text, reply_markup=_menu_buttons())
    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}", reply_markup=_menu_buttons())


async def button_clarify_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """4️⃣ Уточнить / внести правку — просим написать изменение."""
    query = update.callback_query
    await query.answer()
    if not context.user_data.get(USER_BPMN_DATA):
        await query.edit_message_text(
            "Сначала загрузите договор и постройте BPMN, затем можно внести правку.",
            reply_markup=_menu_buttons(),
        )
        return
    context.user_data[USER_AWAITING_CORRECTION] = True
    await query.edit_message_text(
        "Напишите, что изменить в процессе. Например: «добавить шаг перед согласованием» или «убрать этап тестирования»."
    )


async def handle_text_correction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текстовой правки: интерпретация → обновление BPMN → новая схема и меню."""
    if not context.user_data.get(USER_AWAITING_CORRECTION):
        return  # не в режиме правки — игнорируем или можно подсказать «загрузите файл»
    if not update.message or not update.message.text:
        return

    correction = update.message.text.strip()
    if not correction:
        await update.message.reply_text("Напишите текст правки или отмените, нажав «Загрузить новый договор».", reply_markup=_menu_buttons())
        return

    contract_text = context.user_data.get(USER_CONTRACT_TEXT, "")
    bpmn_data = context.user_data.get(USER_BPMN_DATA)
    if not bpmn_data or not contract_text:
        context.user_data[USER_AWAITING_CORRECTION] = False
        await update.message.reply_text("Контекст договора потерян. Загрузите договор заново.", reply_markup=_menu_buttons())
        return

    status_msg = await update.message.reply_text("Учитываю правку и обновляю схему…")
    context.user_data[USER_AWAITING_CORRECTION] = False

    try:
        new_bpmn = update_bpmn_from_correction(contract_text, bpmn_data, correction)
        if new_bpmn:
            context.user_data[USER_BPMN_DATA] = new_bpmn
            await status_msg.delete()
            await _send_bpmn_and_menu(update, context, new_bpmn, caption="BPMN обновлена с учётом вашей правки.")
        else:
            await status_msg.edit_text(
                "Не удалось применить правку к схеме. Попробуйте сформулировать иначе или загрузите новый договор.",
                reply_markup=_menu_buttons(),
            )
    except Exception as e:
        await status_msg.edit_text(f"Ошибка: {e}", reply_markup=_menu_buttons())


async def button_new_contract(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """5️⃣ Загрузить новый договор — сброс контекста и просьба загрузить .doc."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop(USER_CONTRACT_TEXT, None)
    context.user_data.pop(USER_BPMN_DATA, None)
    context.user_data.pop(USER_AWAITING_CORRECTION, None)
    await query.edit_message_text(
        "Контекст сброшен. Загрузите новый файл договора в формате .doc или .docx."
    )


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("Задайте TELEGRAM_BOT_TOKEN в .env")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_correction))
    app.add_handler(CallbackQueryHandler(button_show_bpmn, pattern="^show_bpmn$"))
    app.add_handler(CallbackQueryHandler(button_brief, pattern="^brief$"))
    app.add_handler(CallbackQueryHandler(button_risks, pattern="^risks$"))
    app.add_handler(CallbackQueryHandler(button_clarify_edit, pattern="^clarify_edit$"))
    app.add_handler(CallbackQueryHandler(button_new_contract, pattern="^new_contract$"))

    print("Бот запущен.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
