import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import anthropic

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API ключі
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
LAWYER_PHONE = "+380983607200"
LAWYER_USERNAME = "Law_firm_zakhyst"

# Claude клієнт
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Зберігання нових користувачів
new_users = set()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    text = """🏛️ **Юридичний консультант**

Вітаю! Я надаю професійні юридичні консультації на основі законодавства України.

**Що я можу:**
⚖️ Відповідати на правові питання
📋 Посилатися на закони України
💡 Давати практичні поради
👨‍💼 З'єднувати з адвокатом

**Просто опишіть вашу ситуацію - я проаналізую і дам відповідь!**"""

    keyboard = [[InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="lawyer")]]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка повідомлень"""
    user_id = update.effective_user.id
    message = update.message.text
    username = update.effective_user.first_name or "Користувач"

    # Привітання для нових користувачів
    if user_id not in new_users:
        new_users.add(user_id)
        greeting = f"👋 Вітаю, {username}! Я ваш юридичний консультант. Опишіть вашу правову ситуацію, і я надам професійну консультацію."
        await update.message.reply_text(greeting)

    # Відправка повідомлення про обробку
    processing_msg = await update.message.reply_text("⚖️ Аналізую ваше питання...")

    try:
        # Запит до Claude
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            system="""Ви - кваліфікований юрист України. Аналізуйте кожне повідомлення:

1. ЯКЩО це юридичне питання або правова ситуація:
   - Надайте детальну професійну консультацію
   - Посилайтеся на конкретні статті законів України
   - Структуруйте відповідь: Аналіз → Правова база → Поради
   - Пишіть українською мовою

2. ЯКЩО це НЕ юридичне питання:
   - Відповідайте: "❌ Я консультую тільки з юридичних питань. Опишіть вашу правову ситуацію, і я допоможу з професійною консультацією."

Юридичні питання включають: цивільне, кримінальне, трудове, сімейне, адміністративне право, власність, договори, спадщина, суди, штрафи, порушення прав тощо.""",
            messages=[{"role": "user", "content": message}]
        )

        claude_answer = response.content[0].text

        # Видалення повідомлення про обробку
        await processing_msg.delete()

        # Якщо Claude відповів що це не юридичне питання
        if "❌ Я консультую тільки з юридичних питань" in claude_answer:
            keyboard = [[InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="lawyer")]]
            await update.message.reply_text(claude_answer, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Формування повної відповіді для юридичних питань
        full_response = f"""{claude_answer}

---
👨‍💼 **Потрібна персональна допомога?** 
Наш адвокат готовий надати професійну консультацію та допомогу у вирішенні вашої ситуації."""

        # Кнопки для юридичних консультацій
        keyboard = [
            [InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="lawyer")],
            [InlineKeyboardButton("💰 Питання оплати", callback_data="payment")]
        ]
        
        await update.message.reply_text(
            full_response, 
            reply_markup=InlineKeyboardMarkup(keyboard), 
            parse_mode='Markdown'
        )

    except Exception as e:
        logger.error(f"Помилка: {e}")
        await processing_msg.delete()
        await update.message.reply_text(
            "❌ Технічна помилка. Спробуйте пізніше або зверніться до адвоката.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📞 Адвокат", callback_data="lawyer")]])
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок"""
    query = update.callback_query
    await query.answer()

    if query.data == "lawyer":
        text = f"""📞 **Зв'язок з адвокатом**

**Телефон:** {LAWYER_PHONE}
**Telegram:** @{LAWYER_USERNAME}

🕐 **Режим роботи:** Пн-Пт 9:00-18:00
⚡ **Термінові питання:** За домовленістю

💬 **При зверненні вкажіть:**
• Суть правової ситуації
• Терміновість питання
• Контактні дані"""

        keyboard = [
            [InlineKeyboardButton("💬 Написати @" + LAWYER_USERNAME, url=f"https://t.me/{LAWYER_USERNAME}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data == "payment":
        text = f"""💰 **Питання оплати**

Вартість юридичних послуг обговорюється індивідуально залежно від складності справи.

📞 **Для уточнення вартості:**
• Телефон: {LAWYER_PHONE}
• Telegram: @{LAWYER_USERNAME}

💡 **Перша консультація** може бути безкоштовною."""

        keyboard = [
            [InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="lawyer")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif query.data == "back":
        text = """🏛️ **Юридичний консультант**

Опишіть вашу правову ситуацію, і я надам професійну консультацію з посиланнями на законодавство України."""

        keyboard = [[InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="lawyer")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

def main():
    """Запуск бота"""
    print("🏛️ Запуск юридичного бота...")
    print(f"📞 Адвокат: {LAWYER_PHONE}")
    print(f"💬 Telegram: @{LAWYER_USERNAME}")

    # Створення додатка
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Обробники
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запуск
    print("✅ Бот запущений!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
