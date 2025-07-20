import logging
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.constants import ChatMemberStatus, ParseMode
import anthropic
import json
import os

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфігурація
TELEGRAM_TOKEN = "7820689370:AAG0JG0P1ShEGuesDv6Uy6blncmal6A506Y"
ANTHROPIC_API_KEY = "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"
LAWYER_PHONE = "+380983607200"
LAWYER_TELEGRAM_ID = None  # Поки None для тестування
LAWYER_USERNAME = "Law_firm_zakhyst"
GROUP_CHAT_ID = None  # Поки None для тестування в особистих повідомленнях

# Режим тестування - дозволяє роботу без групи
TESTING_MODE = True

# Ініціалізація Claude клієнта
anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

class LegalGroupBot:
    def __init__(self):
        self.user_conversations = {}  # Зберігає історію розмов користувачів
        self.banned_words = [
            'дурак', 'ідіот', 'тупий', 'дебіл', 'кретин', 'урод', 
            'мудак', 'сука', 'блядь', 'хуй', 'пізда', 'їбати'
        ]
        # Додавання додаткових привітальних фраз для різноманітності
        self.greeting_variants = [
            "👋 **Вітаю, {username}!**\n\n🏛️ Я ваш персональний юридичний консультант!",
            "🤝 **Доброго дня, {username}!**\n\n⚖️ Радий вітати вас у нашій юридичній групі!",
            "👋 **Привіт, {username}!**\n\n🏛️ Готовий допомогти з будь-якими правовими питаннями!"
        ]
        
    async def setup_group_settings(self, context: ContextTypes.DEFAULT_TYPE):
        """Налаштування групи для анонімності"""
        try:
            # Встановлення налаштувань групи (потрібні права адміністратора)
            await context.bot.set_chat_permissions(
                chat_id=GROUP_CHAT_ID,
                permissions={
                    'can_send_messages': True,
                    'can_send_media_messages': False,
                    'can_send_polls': False,
                    'can_send_other_messages': False,
                    'can_add_web_page_previews': False,
                    'can_change_info': False,
                    'can_invite_users': False,
                    'can_pin_messages': False
                }
            )
        except Exception as e:
            logger.error(f"Помилка налаштування групи: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start в особистих повідомленнях"""
        if update.effective_chat.type != 'private':
            return
            
        welcome_text = """
🏛️ **Вітаємо в юридичній консультації!**

🔹 Я надаю безкоштовні юридичні консультації
🔹 Відповіді базуються на чинному законодавстві України
🔹 При необхідності можете зв'язатися з нашим адвокатом

⚖️ **Приєднуйтесь до нашої юридичної групи для отримання консультацій!**

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
            # Отримання історії розмови користувача
            conversation_history = self.user_conversations.get(user_id, [])
            
            # Формування промпту
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
            
            # Створення контексту з історією
            messages = [{"role": "system", "content": system_prompt}]
            
            # Додавання історії розмови
            for msg in conversation_history[-6:]:  # Останні 6 повідомлень
                messages.append({"role": "user" if msg["from"] == "user" else "assistant", "content": msg["text"]})
            
            # Додавання поточного запитання
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
        import random
        
        # Вибір випадкового привітання
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

    async def handle_group_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка повідомлень у групі"""
        # В режимі тестування дозволяємо роботу в особистих повідомленнях
        if TESTING_MODE:
            # Дозволяємо тестування в будь-якому чаті
            pass
        else:
            # Перевірка чи це правильна група
            if GROUP_CHAT_ID and update.effective_chat.id != int(GROUP_CHAT_ID):
                return
            
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name or "Користувач"
        message_text = update.message.text
        
        # Перевірка чи це перше повідомлення користувача
        if user_id not in self.user_conversations:
            # Відправка привітання новому користувачу
            await self.send_greeting(update, context, user_id, username)
            # Ініціалізація історії розмови
            self.user_conversations[user_id] = []
        
        # Перевірка на ненормативну лексику
        if self.contains_profanity(message_text):
            await update.message.delete()
            warning_msg = await update.message.reply_text(
                f"⚠️ @{username}, будь ласка, дотримуйтесь ввічливості в спілкуванні. Ваше повідомлення видалено."
            )
            # Видалити попередження через 10 секунд
            context.job_queue.run_once(
                lambda context: context.bot.delete_message(GROUP_CHAT_ID, warning_msg.message_id),
                when=10
            )
            return

        # Перевірка чи це юридичне запитання
        if not self.is_legal_question(message_text):
            non_legal_responses = [
                "❌ Вибачте, але ваше запитання не стосується юридичної тематики.",
                "🏛️ Я консультую тільки з правових питань. Будь ласка, сформулюйте юридичне запитання.",
                "⚖️ Моя спеціалізація - юридичні консультації. Чим можу допомогти в правових питаннях?"
            ]
            
            import random
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

        # Відправка запитання адміністратору (тільки якщо є LAWYER_TELEGRAM_ID)
        if LAWYER_TELEGRAM_ID:
            try:
                await context.bot.send_message(
                    chat_id=LAWYER_TELEGRAM_ID,
                    text=f"🆕 **Нове юридичне запитання**\n\n"
                         f"👤 **Користувач:** @{username} (ID: {user_id})\n"
                         f"⏰ **Час:** {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                         f"❓ **Запитання:**\n{question}\n\n"
                         f"---\nID запитання: `{question_id}`",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Помилка відправки адміну: {e}")
                # В тестовому режимі продовжуємо роботу навіть без адвоката
            
            await update.message.reply_text(
                "✅ **Ваше запитання обробляється!**\n\n"
                "🤖 Генерую детальну відповідь...\n"
                "⏰ Це займе кілька секунд.\n\n"
                "💡 Після відповіді зможете зв'язатися з адвокатом для персональної консультації."
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

        # Формування фінальної відповіді з рекомендацією адвоката
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

    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка натискань кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        if query.data == "contact_lawyer":
            # Створення клавіатури для вибору способу зв'язку
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
            # Надання номера телефону для дзвінка
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
            # Перенаправлення до приватного чату з адвокатом
            if TESTING_MODE:
                # В тестовому режимі показуємо інструкції
                test_text = f"""
🧪 **ТЕСТОВИЙ РЕЖИМ**

📱 Для зв'язку з адвокатом:
• **Telegram**: @{LAWYER_USERNAME}
• **Телефон**: {LAWYER_PHONE}

⚙️ **Після налаштування групи:**
• Адвокат отримуватиме історію розмов
• Автоматичне перенаправлення до чату
• Передача контексту розмови

💡 **Зараз можете протестувати:**
• Задавання юридичних запитань
• Генерацію відповідей ботом
• Фільтрацію не-юридичних питань
                """
                await query.edit_message_text(test_text, parse_mode='Markdown')
            else:
                await self.initiate_lawyer_chat(update, context, user_id)
            
        elif query.data == "payment_info":
            # Інформація про оплату - перенаправляє до адвоката
            payment_text = """
💰 **Питання щодо оплати послуг**

Для обговорення вартості юридичних послуг та умов співпраці зверніться безпосередньо до нашого адвоката.

📞 Телефон: **{LAWYER_PHONE}**
💬 Або напишіть в особистий чат
            """.format(LAWYER_PHONE=LAWYER_PHONE)
            
            keyboard = [
                [InlineKeyboardButton("📞 Подзвонити", callback_data="call_lawyer")],
                [InlineKeyboardButton("💬 Написати", callback_data="chat_lawyer")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(payment_text, reply_markup=reply_markup, parse_mode='Markdown')

    async def initiate_lawyer_chat(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Ініціювання чату з адвокатом"""
        try:
            # Підготовка історії розмови
            conversation_history = self.user_conversations.get(user_id, [])
            
            if conversation_history:
                # Формування повідомлення з історією для адвоката
                history_text = "📋 **Історія розмови з ботом:**\n\n"
                
                for msg in conversation_history[-10:]:  # Останні 10 повідомлень
                    timestamp = datetime.fromisoformat(msg["timestamp"]).strftime("%H:%M %d.%m")
                    if msg["from"] == "user":
                        history_text += f"👤 **[{timestamp}]**: {msg['text']}\n\n"
                    else:
                        history_text += f"🤖 **[{timestamp}]**: {msg['text'][:200]}{'...' if len(msg['text']) > 200 else ''}\n\n"
                
                # Відправка історії адвокату
                await context.bot.send_message(
                    chat_id=LAWYER_TELEGRAM_ID,
                    text=f"🆕 **Новий клієнт хоче консультацію**\n\n"
                         f"👤 **User ID:** {user_id}\n"
                         f"⏰ **Час:** {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                         f"{history_text}\n"
                         f"---\n💬 **Клієнт очікує на вашу відповідь**",
                    parse_mode='Markdown'
                )
            
            # Повідомлення користувачу
            success_text = """
✅ **Зв'язок з адвокатом встановлено!**

🔄 Ваша розмова з ботом передана адвокату
📱 Очікуйте відповіді в особистих повідомленнях
⏰ Зазвичай відповідаємо протягом робочого дня

💡 Якщо терміново - телефонуйте: **{LAWYER_PHONE}**
            """.format(LAWYER_PHONE=LAWYER_PHONE)
            
            await update.callback_query.edit_message_text(success_text, parse_mode='Markdown')
            
            # Створення посилання для прямого чату з адвокатом
            lawyer_username = await self.get_lawyer_username(context)
            if lawyer_username:
                keyboard = [
                    [InlineKeyboardButton("💬 Перейти до чату", url=f"https://t.me/{lawyer_username}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text="📱 **Прямий зв'язок з адвокатом:**",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            
        except Exception as e:
            logger.error(f"Помилка ініціації чату з адвокатом: {e}")
            await update.callback_query.edit_message_text(
                f"❌ Помилка зв'язку. Зателефонуйте: **{LAWYER_PHONE}**",
                parse_mode='Markdown'
            )

    async def get_lawyer_username(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Отримання username адвоката"""
        try:
            # Спочатку використовуємо збережений username
            return LAWYER_USERNAME
        except:
            # Якщо не вдалося, спробуємо отримати з ID
            try:
                lawyer_info = await context.bot.get_chat(LAWYER_TELEGRAM_ID)
                return lawyer_info.username
            except:
                return LAWYER_USERNAME

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда допомоги"""
        help_text = """
🏛️ **Юридичний бот-консультант**

**Що я можу:**
✅ Надавати юридичні консультації
✅ Посилатися на українське законодавство
✅ З'єднувати з адвокатом для складних справ
✅ Інформувати про правову базу

**Як користуватися:**
1️⃣ Задайте юридичне запитання в групі
2️⃣ Отримайте консультацію з посиланнями на закони
3️⃣ При потребі зв'яжіться з адвокатом

**Команди:**
/start - Початок роботи
/help - Ця довідка
/lawyer - Зв'язок з адвокатом

📞 **Адвокат:** {LAWYER_PHONE}
        """.format(LAWYER_PHONE=LAWYER_PHONE)
        
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def disclaimer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Відмова від відповідальності"""
        disclaimer_text = """
⚖️ **ВІДМОВА ВІД ВІДПОВІДАЛЬНОСТІ**

Даний телеграм-бот надає виключно загальну правову інформацію і не є заміною професійної юридичної консультації.

**Обмеження:**
• Інформація може бути застарілою
• Не враховує всіх нюансів вашої ситуації  
• Не гарантує правильність у 100% випадків
• Не створює відносин адвокат-клієнт

**Рекомендації:**
• Для складних справ зверніться до адвоката
• Перевіряйте інформацію в офіційних джерелах
• Не покладайтесь виключно на поради бота

**Використовуючи бот, ви:**
✅ Розумієте обмеження сервісу
✅ Не покладаєтесь виключно на його поради  
✅ Берете відповідальність за свої рішення

Створено для інформаційних цілей.
        """
        await update.message.reply_text(disclaimer_text, parse_mode='Markdown')

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробка помилок"""
        logger.error(f"Помилка: {context.error}")

def main():
    """Запуск бота"""
    # Створення бота
    legal_bot = LegalGroupBot()
    
    # Створення додатка
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Налаштування групи при старті
    application.job_queue.run_once(
        lambda context: legal_bot.setup_group_settings(context),
        when=1
    )
    
    # Додавання обробників команд
    application.add_handler(CommandHandler("start", legal_bot.start_command))
    application.add_handler(CommandHandler("help", legal_bot.help_command))
    
    # Обробка кнопок
    application.add_handler(CallbackQueryHandler(legal_bot.handle_callback_query))
    
    # Обробка текстових повідомлень (для тестування в особистих повідомленнях)
    if TESTING_MODE:
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            legal_bot.handle_group_message
        ))
    else:
        # Обробка повідомлень тільки у групі
        application.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.GROUPS,
            legal_bot.handle_group_message
        ))
    
    # Обробка помилок
    application.add_error_handler(legal_bot.error_handler)
    
    # Запуск бота
    if TESTING_MODE:
        print("🧪 Юридичний бот запущено в ТЕСТОВОМУ РЕЖИМІ!")
        print("📱 Можете тестувати в особистих повідомленнях")
        print("💬 Надішліть боту /start для початку")
    else:
        print("🏛️ Юридичний груповий бот запущено!")
    
    print(f"📞 Телефон адвоката: {LAWYER_PHONE}")
    print(f"👨‍💼 Username адвоката: @{LAWYER_USERNAME}")
    application.run_polling()

if __name__ == '__main__':
    main()
