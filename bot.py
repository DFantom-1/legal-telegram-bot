#!/usr/bin/env python3
import logging
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import anthropic

# Логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Конфігурація
TOKEN = os.environ.get('TELEGRAM_TOKEN')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY')

if not TOKEN or not ANTHROPIC_KEY:
    logger.error("Відсутні environment variables!")
    exit(1)

# Claude клієнт
try:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    logger.info("Claude клієнт ініціалізовано")
except Exception as e:
    logger.error(f"Помилка ініціалізації Claude: {e}")
    exit(1)

# Телефон адвоката
LAWYER_PHONE = "+380983607200"
LAWYER_USERNAME = "Law_firm_zakhyst"

def start(update, context):
    """Команда /start"""
    keyboard = [[InlineKeyboardButton("📞 Адвокат", callback_data="lawyer")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """🏛️ **Юридичний консультант**

Вітаю! Я надаю професійні консультації з українського права.

Опишіть вашу ситуацію і я дам детальну відповідь з посиланнями на закони."""
    
    update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def handle_message(update, context):
    """Обробка повідомлень"""
    message = update.message.text
    user_name = update.effective_user.first_name or "Користувач"
    
    # Відправка повідомлення про обробку
    processing = update.message.reply_text("⚖️ Аналізую ваше питання...")
    
    try:
        # Запит до Claude
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1500,
            system="""Ви - юрист України. Аналізуйте кожне повідомлення:

ЯКЩО це юридичне питання:
- Надайте професійну консультацію
- Посилайтеся на статті законів України  
- Структуруйте: Аналіз → Правова база → Поради

ЯКЩО це НЕ юридичне питання:
- Відповідайте: "❌ Я консультую тільки з юридичних питань. Опишіть вашу правову ситуацію."

Пишіть українською мовою.""",
            messages=[{"role": "user", "content": message}]
        )
        
        claude_answer = response.content[0].text
        
        # Видалення повідомлення про обробку
        processing.delete()
        
        # Перевірка чи це юридичне питання
        if "❌ Я консультую тільки з юридичних питань" in claude_answer:
            keyboard = [[InlineKeyboardButton("📞 Адвокат", callback_data="lawyer")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(claude_answer, reply_markup=reply_markup)
            return
        
        # Формування відповіді для юридичних питань
        full_response = f"""{claude_answer}

---
👨‍💼 **Потрібна персональна консультація?**
Зверніться до нашого адвоката для детального розгляду справи."""
        
        keyboard = [
            [InlineKeyboardButton("📞 Адвокат", callback_data="lawyer")],
            [InlineKeyboardButton("💰 Оплата", callback_data="payment")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(full_response, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        processing.delete()
        logger.error(f"Помилка: {e}")
        
        keyboard = [[InlineKeyboardButton("📞 Адвокат", callback_data="lawyer")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            "❌ Технічна помилка. Зверніться до адвоката.",
            reply_markup=reply_markup
        )

def button_handler(update, context):
    """Обробка кнопок"""
    query = update.callback_query
    query.answer()
    
    if query.data == "lawyer":
        text = f"""📞 **Контакти адвоката**

**Телефон:** {LAWYER_PHONE}
**Telegram:** @{LAWYER_USERNAME}

🕐 **Графік:** Пн-Пт 9:00-18:00
⚡ **Термінові питання:** За домовленістю

💬 **Опишіть при зверненні:**
• Вашу правову ситуацію
• Терміновість питання
• Контактні дані"""

        keyboard = [
            [InlineKeyboardButton("💬 @" + LAWYER_USERNAME, url=f"https://t.me/{LAWYER_USERNAME}")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif query.data == "payment":
        text = f"""💰 **Вартість послуг**

Вартість залежить від складності справи.

📞 **Для уточнення:**
• Телефон: {LAWYER_PHONE}  
• Telegram: @{LAWYER_USERNAME}

💡 **Перша консультація може бути безкоштовною.**"""

        keyboard = [
            [InlineKeyboardButton("📞 Зв'язатися", callback_data="lawyer")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    elif query.data == "back":
        text = """🏛️ **Юридичний консультант**

Опишіть вашу правову ситуацію і я надам професійну консультацію."""

        keyboard = [[InlineKeyboardButton("📞 Адвокат", callback_data="lawyer")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

def main():
    """Запуск бота"""
    print("🏛️ Запуск юридичного бота...")
    
    # Створення updater
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # Додавання обробників
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    # Запуск
    print("✅ Юридичний бот запущено!")
    print(f"📞 Адвокат: {LAWYER_PHONE}")
    print(f"💬 Telegram: @{LAWYER_USERNAME}")
    
    # Polling
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
