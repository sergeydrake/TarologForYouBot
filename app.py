import logging

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, filters
import random
import sqlite3

from config import BOT_TOKEN, WEBHOOK_URL


# Функции для работы с базой данных
def create_db():
    """Создает базу данных и таблицу пользователей, если они не существуют"""
    conn = sqlite3.connect('tarolog_users.db')  # или укажите путь к базе данных
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        balance REAL)''')
    conn.commit()
    conn.close()


def add_user(user_id, username):
    """Добавляет пользователя в базу данных"""
    conn = sqlite3.connect('tarolog_users.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO users (user_id, username, balance)
                      VALUES (?, ?, ?) ON CONFLICT(user_id) DO NOTHING''', (user_id, username, 0.0))
    conn.commit()
    conn.close()


def get_balance(user_id):
    """Возвращает баланс пользователя"""
    conn = sqlite3.connect('tarolog_users.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT balance FROM users WHERE user_id = ?''', (user_id,))
    balance = cursor.fetchone()
    conn.close()
    return balance[0] if balance else 0.0


def update_balance(user_id, amount):
    """Обновляет баланс пользователя"""
    conn = sqlite3.connect('tarolog_users.db')
    cursor = conn.cursor()
    cursor.execute('''UPDATE users SET balance = balance + ? WHERE user_id = ?''', (amount, user_id))
    conn.commit()
    conn.close()


# Команды для работы с личным кабинетом
async def account(update: Update, context: CallbackContext):
    """Обработка команды /account для отображения баланса пользователя"""
    logger.info("Вызывается функция /account")
    user_id = update.message.from_user.id
    balance = get_balance(user_id)

    keyboard = [
        [
            InlineKeyboardButton("Пополнить счёт", callback_data="replenish"),
            InlineKeyboardButton("Редактировать данные", callback_data="edit_data"),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Ваш баланс: {balance} рублей\n\n"
        "Что вы хотите сделать?",
        reply_markup=reply_markup,
    )


# Инициализация базы данных при запуске бота
create_db()


# Настроим логирование для отслеживания ошибок
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
# Устанавливаем уровень логирования для библиотеки httpx на WARNING
logging.getLogger('httpx').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# Список карт Таро
TARO_CARDS = [
    {"name": "Шут", "upright": "Новые начинания", "reversed": "Безрассудство"},
    {"name": "Маг", "upright": "Сила воли", "reversed": "Манипуляция"},
    {"name": "Жрица", "upright": "Интуиция", "reversed": "Тайны"},
    {"name": "Императрица", "upright": "Творчество", "reversed": "Расточительство"},
    {"name": "Император", "upright": "Стабильность", "reversed": "Контроль"},
]


# Функция для главного меню
async def start(update: Update, context: CallbackContext) -> None:
    logger.info("Вызывается функция /start")

    # Получение данных о пользователе
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    # Добавляем пользователя в базу, если его нет
    add_user(user_id, username)

    keyboard = [
        [
            KeyboardButton("🔮 Сделать расклад"),
            KeyboardButton("🔑 Личный кабинет"),
        ],
        [
            KeyboardButton("ℹ️ О боте"),
            KeyboardButton("❓ Помощь"),
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Добро пожаловать в TarologForYou! Выберите действие:", reply_markup=reply_markup)


# Функция для выполнения расклада
async def spread(update: Update, context: CallbackContext):
    logger.info("Начинается расклад Таро")
    num_cards = 3  # Количество карт в раскладе

    if num_cards > len(TARO_CARDS):
        await update.message.reply_text(
            f"В колоде недостаточно карт. Доступно: {len(TARO_CARDS)}."
        )
        return

    cards = draw_cards(num_cards)
    response = "Ваш расклад:\n"
    for card in cards:
        response += f"- {card['name']} ({card['orientation']}): {card['meaning']}\n"

    # Отправляем результат расклада в ответ на команду
    await update.message.reply_text(response)
    logger.info("Расклад отправлен пользователю")


def draw_cards(num=3):
    """Случайный выбор карт Таро."""
    if num > len(TARO_CARDS):
        raise ValueError(f"Запрошено {num} карт, но в колоде всего {len(TARO_CARDS)}.")

    cards = random.sample(TARO_CARDS, num)
    results = []
    for card in cards:
        orientation = random.choice(["upright", "reversed"])
        results.append({
            "name": card["name"],
            "meaning": card[orientation],
            "orientation": "Прямое" if orientation == "upright" else "Перевернутое"
        })
    return results


# Обработка сообщения "📜 Меню" — нет нужды в дополнительном меню, так как оно уже в кастомной клавиатуре
async def handle_menu(update: Update, context: CallbackContext) -> None:
    # Проверяем, что это сообщение не пустое и что оно не является кнопкой
    if update.message.text == "📜 Меню":
        logger.info("Меню нажато, повторный запрос главного меню")
        # Отправляем главное меню
        await start(update, context)

    elif update.message.text == "🔮 Сделать расклад":
        logger.info("Выполняется расклад")
        await spread(update, context)

    elif update.message.text == "🔑 Личный кабинет":
        logger.info("Переход в личный кабинет")
        await account(update, context)

    elif update.message.text == "ℹ️ О боте":
        logger.info("Информация о боте")
        await update.message.reply_text(
            "Это бот для раскладов Таро. Вы можете сделать расклад и получить консультацию."
        )

    elif update.message.text == "❓ Помощь":
        logger.info("Запрос помощи")
        await update.message.reply_text(
            "Доступные команды:\n"
            "🔮 Сделать расклад — Получить расклад Таро\n"
            "ℹ️ О боте — Информация о боте\n"
            "❓ Помощь — Подсказки по использованию"
        )


# Настройка webhook
async def set_webhook(app):
    await app.bot.set_webhook(url=WEBHOOK_URL)
    logging.info(f"Webhook установлен: {WEBHOOK_URL}")


# Настройка приложения Telegram
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("spread", spread))
    app.add_handler(CommandHandler("account", account))
    app.add_handler(MessageHandler(filters.TEXT, handle_menu))  # Обработчик для всех сообщений

    # Устанавливаем webhook
    app.run_webhook(
        listen="0.0.0.0",
        port=8443,
        url_path=BOT_TOKEN,
        webhook_url=WEBHOOK_URL,
    )


if __name__ == "__main__":
    main()
