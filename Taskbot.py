import telebot
from telebot import types
import sqlite3
import datetime

# ==================== ВСТАВЬТЕ ВАШ ТОКЕН ЗДЕСЬ ====================
BOT_TOKEN = "8209242352:AAFDPaglhBLDc4pMOuWiA5PXdCohKCH8WiA"
# ==================================================================

# Инициализируем бота
bot = telebot.TeleBot(BOT_TOKEN)

# Статусы для кнопок
STATUSES = ['Заказал', 'Ознакомился', 'Отменил']

# Словарь для хранения временных данных пользователей
user_data = {}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            username TEXT,
            first_name TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Сохранение данных в БД
def save_to_db(company_name, status, user_id, username, first_name):
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO companies (company_name, status, user_id, username, first_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (company_name, status, user_id, username, first_name))
    conn.commit()
    conn.close()

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    bot.send_message(
        message.chat.id,
        f"Привет, {user.first_name}!\n"
        "Я помогу вам записать информацию о компании.\n\n"
        "Пожалуйста, введите название компании:"
    )
    
    # Инициализируем словарь для пользователя
    user_data[message.chat.id] = {'step': 'waiting_company_name'}
    bot.register_next_step_handler(message, get_company_name)

# Получение названия компании
def get_company_name(message):
    chat_id = message.chat.id
    
    if chat_id not in user_data:
        user_data[chat_id] = {}
    
    company_name = message.text.strip()
    
    if not company_name:
        bot.send_message(chat_id, "Пожалуйста, введите корректное название компании:")
        bot.register_next_step_handler(message, get_company_name)
        return
    
    user_data[chat_id]['company_name'] = company_name
    user_data[chat_id]['step'] = 'waiting_status'
    
    # Создаем клавиатуру с кнопками статусов
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for status in STATUSES:
        keyboard.add(types.KeyboardButton(status))
    
    bot.send_message(
        chat_id,
        f"Название компании: {company_name}\n"
        "Теперь выберите статус:",
        reply_markup=keyboard
    )
    
    bot.register_next_step_handler(message, get_status)

# Получение статуса и сохранение в БД
def get_status(message):
    chat_id = message.chat.id
    
    if chat_id not in user_data or 'company_name' not in user_data[chat_id]:
        bot.send_message(chat_id, "Произошла ошибка. Пожалуйста, начните заново с /start")
        if chat_id in user_data:
            del user_data[chat_id]
        return
    
    status = message.text.strip()
    
    if status not in STATUSES:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for status_btn in STATUSES:
            keyboard.add(types.KeyboardButton(status_btn))
        
        bot.send_message(
            chat_id,
            "Пожалуйста, выберите один из предложенных статусов:",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(message, get_status)
        return
    
    company_name = user_data[chat_id]['company_name']
    user = message.from_user
    
    # Сохраняем в базу данных
    save_to_db(
        company_name, 
        status, 
        user.id, 
        user.username, 
        user.first_name
    )
    
    # Отправляем подтверждение
    bot.send_message(
        chat_id,
        f"✅ Информация сохранена!\n\n"
        f"🏢 Компания: {company_name}\n"
        f"📊 Статус: {status}\n\n"
        f"Чтобы добавить новую запись, используйте /start",
        reply_markup=types.ReplyKeyboardRemove()  # Убираем клавиатуру
    )
    
    # Очищаем данные пользователя
    if chat_id in user_data:
        del user_data[chat_id]

# Команда для просмотра всех записей
@bot.message_handler(commands=['view'])
def view_all_command(message):
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies ORDER BY created_at DESC')
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        bot.send_message(message.chat.id, "Записей пока нет.")
        return
    
    response = "📋 Все записи:\n\n"
    for record in records:
        response += (
            f"ID: {record[0]}\n"
            f"Компания: {record[1]}\n"
            f"Статус: {record[2]}\n"
            f"Дата: {record[3]}\n"
            f"Пользователь: {record[6] if record[6] else 'N/A'} "
            f"(@{record[5] if record[5] else 'N/A'})\n"
            f"ID пользователя: {record[4]}\n"
            f"{'-'*30}\n"
        )
    
    # Разбиваем на части, если сообщение слишком длинное
    if len(response) > 4096:
        parts = [response[i:i+4096] for i in range(0, len(response), 4096)]
        for part in parts:
            bot.send_message(message.chat.id, part)
    else:
        bot.send_message(message.chat.id, response)

# Команда /help
@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
🤖 *Доступные команды:*

/start - Начать диалог для добавления новой записи
/view - Просмотреть все записи (все пользователи)
/help - Показать это сообщение
/stats - Показать статистику

*Как использовать:*
1. Нажмите /start
2. Введите название компании
3. Выберите статус из предложенных вариантов
4. Информация автоматически сохранится в базу данных
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# Команда /stats для показа статистики
@bot.message_handler(commands=['stats'])
def stats_command(message):
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    
    # Общее количество записей
    cursor.execute('SELECT COUNT(*) FROM companies')
    total = cursor.fetchone()[0]
    
    # Количество по статусам
    stats = {}
    for status in STATUSES:
        cursor.execute('SELECT COUNT(*) FROM companies WHERE status = ?', (status,))
        stats[status] = cursor.fetchone()[0]
    
    # Последние 5 записей
    cursor.execute('SELECT company_name, status, created_at FROM companies ORDER BY created_at DESC LIMIT 5')
    recent = cursor.fetchall()
    
    conn.close()
    
    # Формируем ответ
    response = f"📊 *Статистика базы данных:*\n\n"
    response += f"📈 Всего записей: *{total}*\n\n"
    response += "*Распределение по статусам:*\n"
    for status, count in stats.items():
        response += f"  • {status}: {count}\n"
    
    if recent:
        response += f"\n*Последние 5 записей:*\n"
        for i, record in enumerate(recent, 1):
            response += f"{i}. {record[0]} - {record[1]} ({record[2][:16]})\n"
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

# Команда /my для просмотра своих записей
@bot.message_handler(commands=['my'])
def my_records_command(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT company_name, status, created_at 
        FROM companies 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        bot.send_message(message.chat.id, "У вас пока нет записей.")
        return
    
    response = f"📋 *Ваши записи ({len(records)}):*\n\n"
    for i, record in enumerate(records, 1):
        response += (
            f"{i}. *{record[0]}*\n"
            f"   Статус: {record[1]}\n"
            f"   Дата: {record[2][:16]}\n\n"
        )
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

# Обработчик для всех текстовых сообщений (не команд)
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    
    # Проверяем, находится ли пользователь в процессе ввода
    if chat_id in user_data:
        current_step = user_data[chat_id].get('step')
        
        if current_step == 'waiting_company_name':
            get_company_name(message)
        elif current_step == 'waiting_status':
            get_status(message)
        else:
            bot.send_message(chat_id, "Пожалуйста, используйте команду /start для начала работы.")
    else:
        # Если пользователь просто отправил текст без команды
        bot.send_message(
            chat_id,
            "Я не понял ваше сообщение. Используйте /start для добавления записи или /help для справки."
        )

# Функция для запуска бота
def main():
    print("Инициализация базы данных...")
    init_db()
    print("База данных готова.")
    print("Бот запущен...")
    
    # Запускаем бота
    bot.polling(none_stop=True, interval=0)

if __name__ == '__main__':
    main()