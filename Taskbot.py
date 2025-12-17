import telebot
from telebot import types
import sqlite3
import datetime
import re

# ==================== КОНФИГУРАЦИЯ ====================
BOT_TOKEN = "8209242352:AAFDPaglhBLDc4pMOuWiA5PXdCohKCH8WiA"
ADMIN_CHAT_ID = "7669840193"  # Ваш ID чата в Telegram
# ======================================================

# Инициализируем бота
bot = telebot.TeleBot(BOT_TOKEN)

# Статусы для кнопок
STATUSES = ['Заказал', 'Ознакомился', 'Отменил']

# Словарь для хранения временных данных пользователей
user_data = {}

# Функция для проверки и нормализации Telegram username/ссылки
def normalize_telegram_link(input_text):
    input_text = input_text.strip()
    
    # Удаляем лишние пробелы и преобразуем в нижний регистр
    input_text = input_text.lower().replace(' ', '')
    
    # Если пользователь ввел "пропустить" или аналогичные команды
    if input_text in ['пропустить', 'skip', '-', 'нет', 'no', '']:
        return None
    
    # Если это уже полная ссылка https://t.me/
    if input_text.startswith('https://t.me/'):
        return input_text
    
    # Если это уже полная ссылка t.me/
    if input_text.startswith('t.me/'):
        return 'https://' + input_text
    
    # Если это @username
    if input_text.startswith('@'):
        username = input_text[1:]  # Убираем @
        if username:  # Проверяем, что username не пустой
            return f'https://t.me/{username}'
    
    # Если это просто username без @
    if re.match(r'^[a-zA-Z0-9_]{5,32}$', input_text):
        return f'https://t.me/{input_text}'
    
    # Если ничего не подошло, возвращаем как есть (будет проверено дальше)
    return f'https://t.me/{input_text}'

# Функция для проверки корректности Telegram ссылки/username
def is_valid_telegram_link(input_text):
    if not input_text:
        return False
    
    input_text = input_text.strip().lower()
    
    # Проверяем варианты пропуска
    if input_text in ['пропустить', 'skip', '-', 'нет', 'no', '']:
        return True
    
    # Проверяем полную ссылку
    if input_text.startswith(('https://t.me/', 'http://t.me/', 't.me/')):
        return True
    
    # Проверяем @username или просто username
    if input_text.startswith('@'):
        username = input_text[1:]
    else:
        username = input_text
    
    # Telegram username правила: 5-32 символа, буквы, цифры, underscore
    if re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
        return True
    
    return False

# Инициализация базы данных с проверкой структуры
def init_db():
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    
    # Создаем таблицу, если её нет
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            telegram_link TEXT,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            username TEXT,
            first_name TEXT
        )
    ''')
    
    # Проверяем существование столбца telegram_link
    cursor.execute("PRAGMA table_info(companies)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Если нет столбца telegram_link, добавляем его
    if 'telegram_link' not in columns:
        print("⚠️ Столбец telegram_link отсутствует, добавляем...")
        try:
            cursor.execute("ALTER TABLE companies ADD COLUMN telegram_link TEXT")
            print("✅ Столбец telegram_link успешно добавлен")
        except sqlite3.OperationalError as e:
            print(f"❌ Ошибка при добавлении столбца: {e}")
    
    conn.commit()
    conn.close()

# Сохранение данных в БД
def save_to_db(company_name, telegram_link, status, user_id, username, first_name):
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO companies (company_name, telegram_link, status, user_id, username, first_name)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (company_name, telegram_link, status, user_id, username, first_name))
        conn.commit()
        print(f"✅ Данные сохранены: {company_name}, {telegram_link}, {status}")
    except Exception as e:
        print(f"❌ Ошибка при сохранении в БД: {e}")
        # Если ошибка связана со структурой таблицы, пересоздаем её
        if "no column named" in str(e):
            print("🔄 Пересоздаем таблицу с правильной структурой...")
            cursor.execute("DROP TABLE IF EXISTS companies")
            cursor.execute('''
                CREATE TABLE companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company_name TEXT NOT NULL,
                    telegram_link TEXT,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER,
                    username TEXT,
                    first_name TEXT
                )
            ''')
            cursor.execute('''
                INSERT INTO companies (company_name, telegram_link, status, user_id, username, first_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (company_name, telegram_link, status, user_id, username, first_name))
            conn.commit()
            print("✅ Таблица пересоздана, данные сохранены")
        else:
            raise e
    
    conn.close()

# Функция для отправки данных администратору
def send_to_admin(company_name, telegram_link, status, user_info, chat_id):
    try:
        # Формируем красивое сообщение для администратора
        admin_message = (
            f"📥 *НОВАЯ ЗАПИСЬ ОТ ПОЛЬЗОВАТЕЛЯ*\n\n"
            f"🏢 *Компания:* {company_name}\n"
            f"📱 *Telegram компании:* {telegram_link if telegram_link else '❌ не указан'}\n"
            f"📊 *Статус:* {status}\n"
            f"🕐 *Время:* {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"👤 *Информация о пользователе:*\n"
            f"   • Имя: {user_info['first_name']}\n"
            f"   • Username: @{user_info['username'] if user_info['username'] else 'нет'}\n"
            f"   • ID: {user_info['user_id']}\n"
            f"   • ID чата: {chat_id}\n\n"
            f"📌 *Источник:* пользователь добавил через бота"
        )
        
        # Отправляем сообщение администратору
        bot.send_message(
            ADMIN_CHAT_ID,
            admin_message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        return True
        
    except Exception as e:
        print(f"Ошибка при отправке администратору: {e}")
        return False

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    bot.send_message(
        message.chat.id,
        f"👋 Привет, {user.first_name}!\n"
        "Я помогу вам записать информацию о компании.\n\n"
        "📝 Пожалуйста, введите название компании:"
    )
    
    # Инициализируем словарь для пользователя
    user_data[message.chat.id] = {
        'step': 'waiting_company_name',
        'user_info': {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name
        }
    }
    bot.register_next_step_handler(message, get_company_name)

# Получение названия компании
def get_company_name(message):
    chat_id = message.chat.id
    
    if chat_id not in user_data:
        user_data[chat_id] = {}
    
    company_name = message.text.strip()
    
    if not company_name:
        bot.send_message(chat_id, "❌ Пожалуйста, введите корректное название компании:")
        bot.register_next_step_handler(message, get_company_name)
        return
    
    if len(company_name) > 100:
        bot.send_message(chat_id, "❌ Слишком длинное название. Максимум 100 символов:")
        bot.register_next_step_handler(message, get_company_name)
        return
    
    user_data[chat_id]['company_name'] = company_name
    user_data[chat_id]['step'] = 'waiting_telegram_link'
    
    bot.send_message(
        chat_id,
        f"✅ Название компании: *{company_name}*\n\n"
        "📲 Теперь введите ссылку на Telegram компании:\n"
        "• Можно ввести @username (например: @companyname)\n"
        "• Можно ввести просто username (например: companyname)\n"
        "• Можно ввести полную ссылку (например: https://t.me/companyname)\n"
        "• Можно пропустить, отправив 'пропустить' или '-'",
        parse_mode='Markdown'
    )
    
    bot.register_next_step_handler(message, get_telegram_link)

# Получение ссылки на Telegram компании
def get_telegram_link(message):
    chat_id = message.chat.id
    
    if chat_id not in user_data or 'company_name' not in user_data[chat_id]:
        bot.send_message(chat_id, "❌ Произошла ошибка. Пожалуйста, начните заново с /start")
        if chat_id in user_data:
            del user_data[chat_id]
        return
    
    telegram_input = message.text.strip()
    
    # Проверяем корректность ввода
    if not is_valid_telegram_link(telegram_input):
        bot.send_message(
            chat_id,
            "❌ Неверный формат Telegram ссылки.\n"
            "Пожалуйста, введите корректный:\n"
            "• @username (от 5 до 32 символов: буквы, цифры, _)\n"
            "• username (без @, от 5 до 32 символов)\n"
            "• https://t.me/username\n"
            "• Или отправьте 'пропустить' для продолжения без ссылки"
        )
        bot.register_next_step_handler(message, get_telegram_link)
        return
    
    # Нормализуем ссылку
    if telegram_input.lower() in ['пропустить', 'skip', '-', 'нет', 'no', '']:
        telegram_link = None
    else:
        telegram_link = normalize_telegram_link(telegram_input)
    
    user_data[chat_id]['telegram_link'] = telegram_link
    user_data[chat_id]['step'] = 'waiting_status'
    
    # Создаем клавиатуру с кнопками статусов
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for status in STATUSES:
        keyboard.add(types.KeyboardButton(status))
    
    telegram_info = f"\n📱 Telegram: {telegram_link}" if telegram_link else "\n📱 Telegram: не указан"
    
    bot.send_message(
        chat_id,
        f"🏢 Компания: *{user_data[chat_id]['company_name']}*{telegram_info}\n\n"
        "📊 Теперь выберите статус:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    
    bot.register_next_step_handler(message, get_status)

# Получение статуса, сохранение в БД и отправка администратору
def get_status(message):
    chat_id = message.chat.id
    
    if chat_id not in user_data or 'company_name' not in user_data[chat_id]:
        bot.send_message(chat_id, "❌ Произошла ошибка. Пожалуйста, начните заново с /start")
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
            "❌ Пожалуйста, выберите один из предложенных статусов:",
            reply_markup=keyboard
        )
        bot.register_next_step_handler(message, get_status)
        return
    
    company_name = user_data[chat_id]['company_name']
    telegram_link = user_data[chat_id].get('telegram_link')
    user_info = user_data[chat_id]['user_info']
    
    # Сначала удаляем клавиатуру
    bot.send_message(
        chat_id,
        "⏳ Сохраняю данные...",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    # Сохраняем в базу данных
    save_to_db(
        company_name, 
        telegram_link,
        status, 
        user_info['user_id'], 
        user_info['username'], 
        user_info['first_name']
    )
    
    # Формируем сообщение с результатами для пользователя
    telegram_display = f"[Перейти в Telegram]({telegram_link})" if telegram_link else "не указан"
    
    # Отправляем подтверждение пользователю
    user_message = (
        f"✅ *Ваша информация успешно сохранена!*\n\n"
        f"🏢 *Компания:* {company_name}\n"
        f"📱 *Telegram:* {telegram_display}\n"
        f"📊 *Статус:* {status}\n"
        f"📅 *Время:* {datetime.datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
        f"🔄 Чтобы добавить новую запись, используйте /start\n"
        f"📋 Чтобы посмотреть свои записи, используйте /my"
    )
    
    bot.send_message(
        chat_id,
        user_message,
        parse_mode='Markdown',
        disable_web_page_preview=True
    )
    
    # Отправляем данные администратору
    admin_sent = send_to_admin(company_name, telegram_link, status, user_info, chat_id)
    
    if not admin_sent:
        bot.send_message(
            chat_id,
            "⚠️ Данные сохранены, но возникла ошибка при отправке администратору.",
        )
    
    # Очищаем данные пользователя
    if chat_id in user_data:
        del user_data[chat_id]

# Команда для просмотра всех записей
@bot.message_handler(commands=['view'])
def view_all_command(message):
    # Проверяем, является ли пользователь администратором
    if str(message.chat.id) != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "⛔ Эта команда доступна только администратору.")
        return
    
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM companies ORDER BY created_at DESC')
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        bot.send_message(message.chat.id, "📭 Записей пока нет.")
        return
    
    response = f"📋 *Все записи в базе данных ({len(records)}):*\n\n"
    for record in records:
        telegram_display = f"[📱 Telegram]({record[2]})" if record[2] else "❌ нет ссылки"
        response += (
            f"*ID:* {record[0]}\n"
            f"*🏢 Компания:* {record[1]}\n"
            f"*📱 Ссылка:* {telegram_display}\n"
            f"*📊 Статус:* {record[3]}\n"
            f"*📅 Дата:* {record[4][:16]}\n"
            f"*👤 Пользователь:* {record[7] if record[7] else 'N/A'} "
            f"(@{record[6] if record[6] else 'N/A'})\n"
            f"{'─'*30}\n"
        )
    
    # Разбиваем на части, если сообщение слишком длинное
    if len(response) > 4096:
        parts = [response[i:i+4096] for i in range(0, len(response), 4096)]
        for part in parts:
            bot.send_message(message.chat.id, part, parse_mode='Markdown', disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, response, parse_mode='Markdown', disable_web_page_preview=True)

# Команда для получения статистики (только для администратора)
@bot.message_handler(commands=['stats'])
def stats_command(message):
    # Проверяем, является ли пользователь администратором
    if str(message.chat.id) != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "📊 *Статистика за сегодня:*\n\n")
        # Для обычных пользователей показываем упрощенную статистику
        user_id = message.from_user.id
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect('companies.db')
        cursor = conn.cursor()
        
        # Записи пользователя за сегодня
        cursor.execute('''
            SELECT COUNT(*) 
            FROM companies 
            WHERE user_id = ? AND DATE(created_at) = ?
        ''', (user_id, today))
        user_today = cursor.fetchone()[0]
        
        # Всего записей пользователя
        cursor.execute('SELECT COUNT(*) FROM companies WHERE user_id = ?', (user_id,))
        user_total = cursor.fetchone()[0]
        
        conn.close()
        
        response = (
            f"📊 *Ваша статистика:*\n\n"
            f"📈 Всего ваших записей: *{user_total}*\n"
            f"📅 Записей сегодня: *{user_today}*\n\n"
            f"🔄 Чтобы добавить новую запись, используйте /start\n"
            f"📋 Чтобы посмотреть свои записи, используйте /my"
        )
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
        return
    
    # Полная статистика для администратора
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    
    # Общее количество записей
    cursor.execute('SELECT COUNT(*) FROM companies')
    total = cursor.fetchone()[0]
    
    if total == 0:
        bot.send_message(message.chat.id, "📊 База данных пуста.")
        conn.close()
        return
    
    # Записи за сегодня
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM companies WHERE DATE(created_at) = ?', (today,))
    today_count = cursor.fetchone()[0]
    
    # Количество записей с Telegram ссылками
    cursor.execute('SELECT COUNT(*) FROM companies WHERE telegram_link IS NOT NULL AND telegram_link != ""')
    with_telegram = cursor.fetchone()[0]
    
    # Количество по статусам
    stats = {}
    for status in STATUSES:
        cursor.execute('SELECT COUNT(*) FROM companies WHERE status = ?', (status,))
        stats[status] = cursor.fetchone()[0]
    
    # Количество уникальных пользователей
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM companies')
    unique_users = cursor.fetchone()[0]
    
    # Последние 5 записей
    cursor.execute('SELECT company_name, status, created_at FROM companies ORDER BY created_at DESC LIMIT 5')
    recent = cursor.fetchall()
    
    conn.close()
    
    # Формируем ответ для администратора
    response = f"📊 *Статистика базы данных (админ):*\n\n"
    response += f"📈 Всего записей: *{total}*\n"
    response += f"📅 Записей сегодня: *{today_count}*\n"
    response += f"👥 Уникальных пользователей: *{unique_users}*\n"
    response += f"📱 С Telegram ссылками: *{with_telegram}* ({with_telegram/total*100:.1f}%)\n\n"
    response += "*Распределение по статусам:*\n"
    for status, count in stats.items():
        percentage = (count / total * 100) if total > 0 else 0
        response += f"  • {status}: {count} ({percentage:.1f}%)\n"
    
    if recent:
        response += f"\n📝 *Последние 5 записей:*\n"
        for i, (company, status, created_at) in enumerate(recent, 1):
            response += f"{i}. {company} - {status} ({created_at[:16]})\n"
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown')

# Команда для получения уведомлений о новых записях (только для администратора)
@bot.message_handler(commands=['notify'])
def notify_command(message):
    if str(message.chat.id) != ADMIN_CHAT_ID:
        bot.send_message(message.chat.id, "⛔ Эта команда доступна только администратору.")
        return
    
    # Получаем записи за последний час
    one_hour_ago = (datetime.datetime.now() - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) 
        FROM companies 
        WHERE created_at >= ?
    ''', (one_hour_ago,))
    recent_count = cursor.fetchone()[0]
    
    if recent_count == 0:
        bot.send_message(message.chat.id, "🕐 За последний час новых записей не было.")
    else:
        cursor.execute('''
            SELECT company_name, status, created_at, first_name 
            FROM companies 
            WHERE created_at >= ? 
            ORDER BY created_at DESC
        ''', (one_hour_ago,))
        recent_records = cursor.fetchall()
        
        response = f"🔔 *Новые записи за последний час ({recent_count}):*\n\n"
        for record in recent_records:
            response += (
                f"🏢 *{record[0]}*\n"
                f"   📊 Статус: {record[1]}\n"
                f"   👤 Пользователь: {record[3]}\n"
                f"   🕐 Время: {record[2][11:16]}\n"
                f"{'─'*20}\n"
            )
        
        bot.send_message(message.chat.id, response, parse_mode='Markdown')
    
    conn.close()

# Команда /my для просмотра своих записей
@bot.message_handler(commands=['my'])
def my_records_command(message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect('companies.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT company_name, telegram_link, status, created_at 
        FROM companies 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (user_id,))
    records = cursor.fetchall()
    conn.close()
    
    if not records:
        bot.send_message(message.chat.id, "📭 У вас пока нет записей.")
        return
    
    response = f"📋 *Ваши записи ({len(records)}):*\n\n"
    for i, record in enumerate(records, 1):
        telegram_display = f"[📱 Telegram]({record[1]})" if record[1] else "❌ нет ссылки"
        response += (
            f"{i}. *{record[0]}*\n"
            f"   📊 Статус: {record[2]}\n"
            f"   📱 Ссылка: {telegram_display}\n"
            f"   📅 Дата: {record[3][:16]}\n\n"
        )
    
    bot.send_message(message.chat.id, response, parse_mode='Markdown', disable_web_page_preview=True)

# Команда /help
@bot.message_handler(commands=['help'])
def help_command(message):
    if str(message.chat.id) == ADMIN_CHAT_ID:
        help_text = """
🤖 *Доступные команды (админ):*

/start - Начать диалог для добавления новой записи
/view - Просмотреть ВСЕ записи (только админ)
/my - Просмотреть только свои записи
/stats - Полная статистика (только админ)
/notify - Новые записи за последний час (только админ)
/help - Показать это сообщение

*Как использовать:*
1. Пользователь использует /start
2. Все данные сохраняются в БД
3. Вы получаете уведомление о новой записи
"""
    else:
        help_text = """
🤖 *Доступные команды:*

/start - Начать диалог для добавления новой записи
/my - Просмотреть только свои записи
/stats - Ваша статистика
/help - Показать это сообщение

*Как использовать:*
1. Нажмите /start
2. Введите название компании
3. Введите Telegram компании (или отправьте 'пропустить')
4. Выберите статус из предложенных вариантов
5. Данные сохранятся и будут отправлены администратору
"""
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

# Обработчик для всех текстовых сообщений (не команд)
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    
    # Проверяем, находится ли пользователь в процессе ввода
    if chat_id in user_data:
        current_step = user_data[chat_id].get('step')
        
        if current_step == 'waiting_company_name':
            get_company_name(message)
        elif current_step == 'waiting_telegram_link':
            get_telegram_link(message)
        elif current_step == 'waiting_status':
            get_status(message)
        else:
            bot.send_message(chat_id, "❌ Пожалуйста, используйте команду /start для начала работы.")
    else:
        # Если пользователь просто отправил текст без команды
        bot.send_message(
            chat_id,
            "🤔 Я не понял ваше сообщение.\n"
            "Используйте /start для добавления записи или /help для справки."
        )

# Функция для запуска бота
def main():
    # Проверяем наличие токена и ID администратора
    if BOT_TOKEN == "ВАШ_ТОКЕН_БОТА_ЗДЕСЬ":
        print("❌ ОШИБКА: Замените BOT_TOKEN на ваш токен бота!")
        return
    
    if ADMIN_CHAT_ID == "ВАШ_CHAT_ID_ЗДЕСЬ":
        print("❌ ОШИБКА: Замените ADMIN_CHAT_ID на ваш ID чата!")
        print("📱 Как получить ваш Chat ID:")
        print("1. Отправьте любое сообщение боту @userinfobot")
        print("2. Он покажет ваш Chat ID")
        return
    
    print("🚀 Инициализация базы данных...")
    init_db()
    print("✅ База данных готова.")
    print(f"👑 Администратор: {ADMIN_CHAT_ID}")
    print("🤖 Бот запущен...")
    print("📱 Ожидание сообщений...")
    
    # Отправляем сообщение администратору о запуске бота
    try:
        bot.send_message(
            ADMIN_CHAT_ID,
            "✅ Бот успешно запущен и готов к работе!\n"
            "Я буду отправлять вам все новые записи от пользователей.\n\n"
            "Используйте /help для списка команд.",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"⚠️ Не удалось отправить сообщение администратору: {e}")
        print("Проверьте правильность ADMIN_CHAT_ID")
    
    # Запускаем бота
    bot.polling(none_stop=True, interval=0)

if __name__ == '__main__':
    main()