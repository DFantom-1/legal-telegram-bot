import logging
import asyncio
import re
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import anthropic
import random

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація з змінних середовища
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '7820689370:AAG0JG0P1ShEGuesDv6Uy6blncmal6A506Y')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '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')
LAWYER_PHONE = "+380983607200"
LAWYER_USERNAME = "Law_firm_zakhyst"

# Ініціалізація Claude клієнта
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

class LegalBot:
    def __init__(self):
        self.user_conversations = {}
        self.banned_words = [
            'дурак', 'ідіот', 'тупий', 'дебіл', 'кретин', 'урод', 
            'мудак', 'сука', 'блядь', 'хуй', 'пізда', 'їбати'
        ]
        self.greeting_variants = [
            "👋 **Вітаю, {username}!**\n\n🏛️ Я ваш персональний юридичний консультант!",
            "🤝 **Доброго дня, {username}!**\n\n⚖️ Радий вітати вас у нашій юридичній групі!",
            "👋 **Привіт, {username}!**\n\n🏛️ Готовий допомогти з будь-якими правовими питаннями!"
        ]

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        welcome_text = """
🏛️ **Вітаємо в юридичній консультації!**

🔹 Я надаю безкоштовні юридичні консультації
🔹 Відповіді базуються на чинному законодавстві України
🔹 При необхідності можете зв'язатися з нашим адвокатом

⚖️ **Задавайте будь-які юридичні запитання!**

📞 Зв'язатися з адвокатом: /lawyer
        """
        
        keyboard = [
            [InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="contact_lawyer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

    def is_legal_question(self, text: str) -> bool:
        """Перевірка чи стосується запитання юридичної тематики"""
        legal_keywords = [
            'закон', 'право', 'суд', 'позов', 'договір', 'штраф', 'порушення',
            'юрист', 'адвокат', 'кодекс', 'стаття', 'норма', 'правопорушення',
            'відшкодування', 'компенсація', 'позбавлення', 'покарання', 'статут',
            'трудов', 'сімейн', 'цивільн', 'кримінальн', 'адміністративн',
            'власність', 'спадщина', 'аліменти', 'розлучення', 'шлюб',
            'житло', 'оренда', 'купівля', 'продаж', 'борг', 'кредит',
            'страхування', 'пенсія', 'соціальн', 'освіт', 'медицин'
        ]
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in legal_keywords)

    def contains_profanity(self, text: str) -> bool:
        """Перевірка на ненормативну лексику"""
        text_lower = text.lower()
        return any(word in text_lower for word in self.banned_words)

    async def get_claude_response(self, question: str, user_id: int) -> str:
        """Отримання відповіді від Claude"""
        try:
            conversation_history = self.user_conversations.get(user_id, [])
            
            system_prompt = """
Ви - кваліфікований юрист в Україні. Надавайте професійні юридичні консультації українською мовою.

ОБОВ'ЯЗКОВІ ВИМОГИ:
1. Відповідайте тільки на юридичні запитання
2. Посилайтеся на конкретні норми українського законодавства
3. Надавайте практичні поради
4. Структуруйте відповідь чітко та зрозуміло
5. Завжди рекомендуйте звернутися до адвоката у складних випадках

ФОРМАТ ВІДПОВІДІ:
📋 Коротка відповідь
⚖️ Правова база (посилання на закони/кодекси)
💡 Практичні поради
⚠️ Застереження (якщо потрібно)

НЕ відповідайте на запитання, що не стосуються права.
            """
            
            messages = [{"role": "system", "content": system_prompt}]
            
            # Додавання історії розмови
            for msg in conversation_history[-6:]:
                messages.append({
                    "role": "user" if msg["from"] == "user" else "assistant", 
                    "content": msg["text"]
                })
            
            messages.append({"role": "user", "content": question})
            
            response = anthropic_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1500,
                messages=messages
            )
            
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Помилка Claude API: {e}")
            return "❌ Вибачте, виникла технічна помилка. Спробуйте пізніше або зверніться до нашого адвоката."

    async def send_greeting(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str):
        """Відправка привітання новому користувачу"""
        greeting_start = random.choice(self.greeting_variants).format(username=username)
        
        greeting_text = f"""
{greeting_start}

**Що я можу:**
⚖️ Надавати юридичні консультації
📋 Посилатися на українське законодавство  
👨‍💼 З'єднувати з кваліфікованим адвокатом
💡 Давати практичні поради

**Як отримати консультацію:**
✍️ Просто напишіть своє юридичне запитання, і я надам детальну відповідь з посиланнями на закони України.

🔹 **Приклади запитань:**
• "Чи може роботодавець звільнити за прогул?"
• "Як оформити спадщину?"
• "Що робити при порушенні прав споживача?"

📞 **Потрібна персональна консультація?** Завжди можете зв'язатися з нашим адвокатом!
        """
        
        keyboard = [
            [InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="contact_lawyer")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(greeting_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка всіх повідомлень"""
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name or "Користувач"
        message_text = update.message.text
        
        # Перевірка чи це перше повідомлення користувача
        if user_id not in self.user_conversations:
            await self.send_greeting(update, context, user_id, username)
            self.user_conversations[user_id] = []
        
        # Перевірка на ненормативну лексику
        if self.contains_profanity(message_text):
            await update.message.reply_text(
                f"⚠️ {username}, будь ласка, дотримуйтесь ввічливості в спілкуванні."
            )
            return

        # Перевірка чи це юридичне запитання
        if not self.is_legal_question(message_text):
            non_legal_responses = [
                "❌ Вибачте, але ваше запитання не стосується юридичної тематики.",
                "🏛️ Я консультую тільки з правових питань. Будь ласка, сформулюйте юридичне запитання.",
                "⚖️ Моя спеціалізація - юридичні консультації. Чим можу допомогти в правових питаннях?"
            ]
            
            response = random.choice(non_legal_responses)
            
            keyboard = [
                [InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="contact_lawyer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(response, reply_markup=reply_markup)
            return

        # Збереження запитання в історію
        self.user_conversations[user_id].append({
            "from": "user",
            "text": message_text,
            "timestamp": datetime.now().isoformat()
        })

        # Повідомлення про обробку
        await update.message.reply_text(
            "✅ **Ваше запитання обробляється!**\n\n"
            "🤖 Генерую детальну відповідь...\n"
            "⏰ Це займе кілька секунд.",
            parse_mode='Markdown'
        )

        # Показати індикатор набору
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

        # Отримання відповіді від Claude
        claude_response = await self.get_claude_response(message_text, user_id)
        
        # Збереження відповіді в історію
        self.user_conversations[user_id].append({
            "from": "bot",
            "text": claude_response,
            "timestamp": datetime.now().isoformat()
        })

        # Формування фінальної відповіді
        final_response = f"""
{claude_response}

---
👨‍💼 **Потрібна персональна консультація або допомога у вирішенні ситуації?**
Наш кваліфікований адвокат готовий надати професійну допомогу!
        """
        
        # Клавіатура з кнопками
        keyboard = [
            [InlineKeyboardButton("📞 Зв'язатися з адвокатом", callback_data="contact_lawyer")],
            [InlineKeyboardButton("💰 Питання про оплату", callback_data="payment_info")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Відправка відповіді
        await update.message.reply_text(final_response, reply_markup=reply_markup, parse_mode='Markdown')

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка натискань кнопок"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "contact_lawyer":
            keyboard = [
                [InlineKeyboardButton("📞 Подзвонити", callback_data="call_lawyer")],
                [InlineKeyboardButton("💬 Написати", callback_data="chat_lawyer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📞 **Зв'язок з адвокатом**\n\nОберіть спосіб зв'язку:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        elif query.data == "call_lawyer":
            phone_text = f"""
📞 **Телефон для зв'язку з адвокатом:**

**{LAWYER_PHONE}**

🕐 **Режим роботи:** Пн-Пт 9:00-18:00
⏰ **Термінові питання:** За домовленістю

💡 Якщо не відповідаємо - залиште повідомлення або скористайтесь чатом.
            """
            
            keyboard = [
                [InlineKeyboardButton("💬 Написати в чат", callback_data="chat_lawyer")],
                [InlineKeyboardButton("🔙 Назад", callback_data="contact_lawyer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(phone_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        elif query.data == "chat_lawyer":
            chat_text = f"""
💬 **Зв'язок з адвокатом в Telegram:**

Напишіть нашому адвокату: @{LAWYER_USERNAME}

📱 **Що включити в повідомлення:**
• Коротко опишіть вашу ситуацію
• Вкажіть терміновість питання
• Додайте контактні дані

⚖️ **Адвокат надасть:**
• Професійну консультацію
• Практичні поради
• Допомогу у вирішенні справи
            """
            
            keyboard = [
                [InlineKeyboardButton("📱 Написати @" + LAWYER_USERNAME, url=f"https://t.me/{LAWYER_USERNAME}")],
                [InlineKeyboardButton("📞 Подзвонити", callback_data="call_lawyer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(chat_text, reply_markup=reply_markup, parse_mode='Markdown')
            
        elif query.data == "payment_info":
            payment_text = f"""
💰 **Питання щодо оплати послуг**

Для обговорення вартості юридичних послуг та умов співпраці зверніться безпосередньо до нашого адвоката.

📞 Телефон: **{LAWYER_PHONE}**
💬 Telegram: @{LAWYER_USERNAME}

💡 **Перша консультація** може бути безкоштовною залежно від складності питання.
            """
            
            keyboard = [
                [InlineKeyboardButton("📞 Подзвонити", callback_data="call_lawyer")],
                [InlineKeyboardButton("💬 Написати", callback_data="chat_lawyer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда допомоги"""
        help_text = f"""
🏛️ **Юридичний бот-консультант**

**Що я можу:**
✅ Надавати юридичні консультації
✅ Посилатися на українське законодавство
✅ З'єднувати з адвокатом для складних справ
✅ Інформувати про правову базу

**Як користуватися:**
1️⃣ Задайте юридичне запитання
2️⃣ Отримайте консультацію з посиланнями на закони
3️⃣ При потребі зв'яжіться з адвокатом

**Команди:**
/start - Початок роботи
/help - Ця довідка

📞 **Адвокат:** {LAWYER_PHONE}
💬 **Telegram:** @{LAWYER_USERNAME}
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка помилок"""
        logger.error(f"Update {update} caused error {context.error}")

def main():
    """Запуск бота"""
    # Створення бота
    legal_bot = LegalBot()
    
    # Створення додатка
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Додавання обробників
    app.add_handler(CommandHandler("start", legal_bot.start_command))
    app.add_handler(CommandHandler("help", legal_bot.help_command))
    app.add_handler(CallbackQueryHandler(legal_bot.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, legal_bot.handle_message))
    
    # Обробка помилок
    app.add_error_handler(legal_bot.error_handler)
    
    # Запуск бота
    print("🏛️ Юридичний бот запущено!")
    print(f"📞 Телефон адвоката: {LAWYER_PHONE}")
    print(f"💬 Telegram адвоката: @{LAWYER_USERNAME}")
    
    # Запуск в режимі polling
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
