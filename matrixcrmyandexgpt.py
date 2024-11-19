import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, filters
import logging
import iam_token_manager  # Импортируем наш модуль для работы с IAM токенами

# Настройки
CATALOG_ID = "b1gb9k14k5ui80g91tnp"
MODEL_URI = f"gpt://{CATALOG_ID}/yandexgpt/rc"
TELEGRAM_TOKEN = "7828823061:AAFqiiM3bQhB2Ab1hidTMXaziGDCps5H3N4"
CHANNEL_ID = "@matrixcrm"  # Замените на ID вашего канала

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Функция для генерации текста с использованием YandexGPT
def generate_text(user_description):
    iam_token = iam_token_manager.get_iam_token()  # Получаем актуальный IAM токен

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {iam_token}"
    }
    prompt = {
        "modelUri": MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": 0.6,
            "maxTokens": 2000
        },
        "messages": [
            {
                "role": "system",
                "text": (
                    "Пиши слово MatrixCRM слитно ты все время пишешь Matrix CRM"
                    "Ты помощник компании MatrixCRM. Твоя задача — создавать текстовые описания обновлений CRM-системы. "
                    "Сообщения должны быть объёмными, детализированными и полезными. "
                    "Каждое сообщение должно начинаться с яркого заголовка с эмодзи, привлекающим внимание, например: '🚀 Обновление Matrix CRM!'. "
                    "Далее идёт краткое введение, поясняющее, что это за обновление и как оно улучшает работу пользователей. "
                    "Каждое новое обновление должно сопровождаться тематическим смайлом, например, если речь идет о записи, ты публикуешь смайлик часов. "
                    "После этого перечисляются все ключевые изменения в виде списка. Каждый пункт должен сопровождаться тематическим смайлом, "
                    "а также содержать подробное описание и пример использования новой функции. Используй только тематические смайлы, связанные с функциями CRM. "
                    "Сообщение завершается позитивным заключением, вдохновляющим пользователей продолжать пользоваться MatrixCRM. "
                    "В конце каждого поста обязательно добавляй хэштеги: #MatrixCRM #Обновления #УправлениеКлиентами #Эффективность."
                )
            },
            {
                "role": "user",
                "text": user_description
            }
        ]
    }
    response = requests.post(url, headers=headers, json=prompt)
    if response.status_code == 200:
        return response.json()["result"]["alternatives"][0]["message"]["text"]
    else:
        return f"Ошибка {response.status_code}: {response.text}"

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Добро пожаловать! Введите краткое описание обновлений для CRM:")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_description = update.message.text.strip()
    if not user_description:
        await update.message.reply_text("Пожалуйста, введите описание обновлений.")
        return

    await update.message.reply_text("Генерирую текст для публикации...")
    generated_text = generate_text(user_description)

    keyboard = [
        [InlineKeyboardButton("Утвердить", callback_data="approve")],
        [InlineKeyboardButton("Регенерировать", callback_data="regenerate")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.user_data["last_description"] = user_description
    context.user_data["generated_text"] = generated_text
    await update.message.reply_text(f"Сгенерированный текст:\n\n{generated_text}", reply_markup=reply_markup)

# Обработчик кнопок
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "approve":
        # Предложение опубликовать после утверждения
        context.user_data["approved_text"] = context.user_data['generated_text']
        keyboard = [
            [InlineKeyboardButton("Опубликовать", callback_data="publish")],
            [InlineKeyboardButton("Отменить", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"✅ Текст утверждён:\n\n{context.user_data['approved_text']}\n\nОпубликовать?", reply_markup=reply_markup)

    elif query.data == "publish":
        # Публикация текста в канал
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=context.user_data["approved_text"])
            await query.edit_message_text(f"✅ Сообщение опубликовано в канал:\n\n{context.user_data['approved_text']}")
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка публикации: {e}")
            logger.error(f"Ошибка публикации в канал: {e}")

    elif query.data == "cancel":
        # Отмена публикации
        await query.edit_message_text("❌ Публикация отменена.")
    elif query.data == "regenerate":
        await query.edit_message_text("Введите новый текст для регенерации:")
        context.user_data["waiting_for_regeneration"] = True

# Обработчик текстов для регенерации
async def regenerate_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for_regeneration"):
        user_description = update.message.text.strip()
        if not user_description:
            await update.message.reply_text("Пожалуйста, введите описание обновлений.")
            return

        await update.message.reply_text("Регенерирую текст...")
        generated_text = generate_text(user_description)

        keyboard = [
            [InlineKeyboardButton("Утвердить", callback_data="approve")],
            [InlineKeyboardButton("Регенерировать", callback_data="regenerate")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        context.user_data["generated_text"] = generated_text
        context.user_data["waiting_for_regeneration"] = False
        await update.message.reply_text(f"Сгенерированный текст:\n\n{generated_text}", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Я не жду текстового ввода. Используйте /start для начала.")

# Запуск бота
def main():
    iam_token_manager.start_token_updater()  # Запуск автообновления IAM токена
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT, regenerate_message))

    app.run_polling()

if __name__ == "__main__":
    main()
