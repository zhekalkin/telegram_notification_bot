import sqlite3
import telebot
from config import token
from datetime import datetime, timedelta
import time
from threading import Thread

# Создание экземпляра бота
bot = telebot.TeleBot(token) #хранится в config.py в папке с проектом

# Функция проверки пользователя
def is_user_allowed(chat_id):
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("SELECT 1 FROM white_list WHERE chat_id = ?", (chat_id,))
    #Запрос выше проверит, хранится ли chat_id пользователя в таблице white_list
    result = cur.fetchone()
    db.close()
    return result is not None

# Функция для получения chat_id, необходима для отправки сообщений в чат, куда был добавлен бот
#chat_id будет необходим для отправки сообщений в нужную группу
def get_chat_id():
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("SELECT id_chat FROM chat")
    result = cur.fetchone()
    db.close()
    if result:
        return result[0]
    return None

# Декоратор для проверки доступа, если функция is_user_allowed вернула True, то разрешаем использование команды
def access_control(func):
    def wrapper(message):
        if message.chat.type == "private" or is_user_allowed(message.chat.id):
            return func(message)
        else:
            bot.send_message(message.chat.id, "Доступ отклонен! Пользоваться ботом могут только администраторы.")
    return wrapper

# Обработчик команд /start и /help
@bot.message_handler(commands=['start', 'help'])
#на каждый обработчик команды вызываем функцию проверки доступа
@access_control
def send_welcome(message):
    helptext = ("👋Здравствуйте, это служебный бот рассылки информации о предстоящих событиях. \n"
                "Для начала использования бот необходимо настроить, пожалуйста, пропишите команду /chats\n"
                "Управление встречей: \n"
                "/addmeet - Добавить встречу \n"
                "/cancel - Отменить встречу в текущий день 🚫 \n"
                "/delete - Удалить встречу. \n"
                "/stop - Завершить встречу. ✅ \n"
                "/edittime - Изменить время встречи \n"
                "Прочее:\n"
                "/list_plane - Список запланированных встреч \n"
                "/list - Список всех проведенных встреч \n"
                "/addadmin - Добавить администратора"
                "/deleteadmin - Удалить администратора \n"
                "/adminlist - Список администраторов")
    
    bot.send_message(message.chat.id, helptext)

@bot.message_handler(commands=['chats'])
@access_control
def send_guide(message):
    guide_text = ("Для начала работы вам необходимо: \n"
    "1. Убедиться, что предыдущие чаты были удалены из БД, если нет, то пропишите /deletechat.  \n"
    "2. Добавить бота в нужный чат и узнать chat_id нужной беседы. \n"
    "3. Прописать команду /addchat и вписать chat_id, куда бот был добавлен. \n"
    "4. Перезапустить скрипт бота. \n"
    "На данный момент бот может работать только с одним чатом! \n")
    db = sqlite3.connect('stb_bot.db')
    cur  = db.cursor()
    cur.execute("SELECT * FROM chat")
    result  = cur.fetchone()
    bot.send_message(message.chat.id, result)
    bot.send_message(message.chat.id, guide_text)
# Обработчик команды для ручного напоминания о встречах
@bot.message_handler(commands=['remember'])
#Функция проверки доступа не вызывается, эта команда доступна в чате всем участникам
def send_remember(message): #функция отправки напоминания
    if datetime.now().weekday() >= 5:  # Если сегодня суббота или воскресенье
        bot.send_message(message.chat.id, "Сегодня выходной день, напоминания не отправляются.")
        return
    
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("SELECT naming, time FROM PlaneMeets WHERE status = 1") #проверяет, включено ли напоминание, если значение 0, то его..
    #..отключил администратор
    meets = cur.fetchall()
    db.close()
    
    for meet in meets:
        naming, time = meet
        planemeet_pre = f"Напоминаем о встрече {naming}, она пройдет в {time}"
        bot.send_message(message.chat.id, planemeet_pre)

# Обработчик команды для добавления администратора
@bot.message_handler(commands=['addadmin'])
@access_control
def add_admin(message):
    msg = bot.send_message(message.chat.id, "Введите ID администратора:")
    bot.register_next_step_handler(msg, save_admin_id)

def save_admin_id(message):
    admin_id = message.text
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("INSERT INTO white_list (chat_id) VALUES (?)", (admin_id,))
    db.commit()
    db.close()
    bot.send_message(message.chat.id, f"Администратор с ID {admin_id} был успешно добавлен.")

# Обработчик команды для удаления администратора
@bot.message_handler(commands=['deleteadmin'])
@access_control
def delete_admin(message):
    msg = bot.send_message(message.chat.id, "Введите ID администратора, которого хотите удалить:")
    bot.register_next_step_handler(msg, remove_admin_id)

def remove_admin_id(message):
    admin_id = message.text
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("DELETE FROM white_list WHERE chat_id = ?", (admin_id,))
    db.commit()
    db.close()
    bot.send_message(message.chat.id, f"Администратор с ID {admin_id} был успешно удален.")


# Функция отправки оповещений за 30 и 15 минут до начала мероприятия
def send_prepared_info():
    chat_id = get_chat_id()
    if chat_id is None:
        print("Ошибка: не удалось получить chat_id.")
        return
    
    while True:
        current_time = datetime.now()
        
        if current_time.weekday() >= 5:  # Если сегодня суббота или воскресенье
            time.sleep(3600)  # Спим 1 час перед следующей проверкой
            continue
        
        db = sqlite3.connect('stb_bot.db')
        cur = db.cursor()
        cur.execute("SELECT id, naming, time FROM PlaneMeets WHERE status = 1")
        meets = cur.fetchall()
        db.close()

        for meet in meets:
            meet_id, naming, time_str = meet
            if is_meeting_canceled_today(meet_id):
                continue
            meet_time = datetime.strptime(time_str, "%H:%M").time()
            meet_datetime = datetime.combine(current_time.date(), meet_time)
            
            if current_time > meet_datetime:
                continue
            
            time_diffs = [
                ("30 минут", meet_datetime - timedelta(minutes=30)),
                ("15 минут", meet_datetime - timedelta(minutes=15)),
            ]
            
            for diff_text, reminder_time in time_diffs:
                if current_time >= reminder_time and current_time < (reminder_time + timedelta(minutes=1)):
                    planemeet_pre = f"Напоминаем о встрече {naming}, она пройдет в {time_str} ({diff_text} до начала)"
                    bot.send_message(chat_id, planemeet_pre)
                    time.sleep(60)  # Ждем 60 секунд перед следующей проверкой

        time.sleep(1)

# Функция отправки оповещений в момент начала мероприятия
def send_start_notification():
    chat_id = get_chat_id()
    if chat_id is None:
        print("Ошибка: не удалось получить chat_id.")
        return
    
    while True:
        current_time = datetime.now()
        
        if current_time.weekday() >= 5:  # Если сегодня суббота или воскресенье
            time.sleep(3600)  # Спим 1 час перед следующей проверкой
            continue
        
        db = sqlite3.connect('stb_bot.db')
        cur = db.cursor()
        cur.execute("SELECT id, naming, time FROM PlaneMeets WHERE status = 1")
        meets = cur.fetchall()
        db.close()

        for meet in meets:
            meet_id, naming, time_str = meet
            if is_meeting_canceled_today(meet_id):
                continue
            meet_time = datetime.strptime(time_str, "%H:%M").time()
            meet_datetime = datetime.combine(current_time.date(), meet_time)
            
            if current_time >= meet_datetime and current_time < (meet_datetime + timedelta(minutes=1)):
                planemeet_pre = f"Напоминаем о встрече {naming}, она началась в {time_str}."
                bot.send_message(chat_id, planemeet_pre)
                time.sleep(60)  # Ждем 60 секунд перед следующей проверкой

        time.sleep(1)

# Обработчик команды для добавления нового чата
@bot.message_handler(commands=['addchat'])
@access_control
def add_chat(message):
    msg = bot.send_message(message.chat.id, "Введите id чата (узнать можно тут: @LeadConverterToolkitBot):")
    bot.register_next_step_handler(msg, save_chat_id)

def save_chat_id(message):
    chat_id = message.text
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("INSERT INTO chat (id_chat) VALUES (?)", (chat_id,))
    db.commit()
    db.close()
    send_result(message)

def send_result(message):
    bot.send_message(message.chat.id, "Бот настроен для использования в чате. \n"
                                      "Теперь просто пригласите его в нужный чат.")

# Обработчик команды для удаления чата
@bot.message_handler(commands=['deletechat'])
@access_control
def delete_chat(message):
    msg = bot.send_message(message.chat.id, "Введите id чата, который хотите удалить:")
    bot.register_next_step_handler(msg, remove_chat_id)

def remove_chat_id(message):
    chat_id = message.text
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("DELETE FROM chat WHERE id_chat = ?", (chat_id,))
    db.commit()
    db.close()
    bot.send_message(message.chat.id, f"Чат с id {chat_id} был успешно удален.")

# Команда для добавления новой встречи
@bot.message_handler(commands=['addmeet'])
@access_control
def add_meet(message):
    msg = bot.send_message(message.chat.id, "Введите название встречи:")
    bot.register_next_step_handler(msg, get_meet_name)

def get_meet_name(message):
    meet_name = message.text
    msg = bot.send_message(message.chat.id, "Введите время встречи (формат ЧЧ:ММ):")
    bot.register_next_step_handler(msg, get_meet_time, meet_name)

def get_meet_time(message, meet_name):
    meet_time = message.text
    insert_meet(meet_name, meet_time)
    bot.send_message(message.chat.id, "Встреча успешно добавлена! Я напомню о ней за 30 и за 15 минут до ее начала. \n"
                                      "Это можете сделать и вы в любой момент, прописав команду /remember")

# Вставка данных в таблицу PlaneMeets
def insert_meet(naming, time_):
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    
    cur.execute("INSERT INTO PlaneMeets (naming, time, status) VALUES (?, ?, 1)", (naming, time_))
    
    db.commit()
    db.close()

# Команда для отмены встречи на текущий день
@bot.message_handler(commands=['cancel'])
@access_control
def cancel_meet(message):
    try:
        msg = bot.send_message(message.chat.id, "ID встречи вы можете узнать, прописав команду /list_plane")
        msg = bot.send_message(message.chat.id, "Введите ID встречи, которую хотите отменить на сегодня:")
        bot.register_next_step_handler(msg, get_meet_id_for_cancel_today)
    except Exception as ex:
        bot.send_message(message.chat.id, "Отмена прервана, но вы всегда можете начать заново!")

def get_meet_id_for_cancel_today(message):
    try:
        meet_id = int(message.text)
        cancel_meeting_today(meet_id)
        bot.send_message(message.chat.id, f"Встреча с ID {meet_id} была успешно отменена на сегодня!")
    except Exception as ex:
        bot.send_message(message.chat.id, "Отмена прервана, но вы всегда можете начать заново!")

def cancel_meeting_today(meet_id):
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    
    today_date = datetime.now().date().strftime("%Y-%m-%d")
    cur.execute("INSERT INTO CanceledMeetings (meet_id, cancel_date) VALUES (?, ?)", (meet_id, today_date))
    
    db.commit()
    db.close()

# Проверка, отменена ли встреча на текущий день
def is_meeting_canceled_today(meet_id):
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    
    today_date = datetime.now().date().strftime("%Y-%m-%d")
    cur.execute("SELECT 1 FROM CanceledMeetings WHERE meet_id = ? AND cancel_date = ?", (meet_id, today_date))
    result = cur.fetchone()
    
    db.close()
    return result is not None

# Команда для изменения времени встречи
@bot.message_handler(commands=['edittime'])
@access_control
def edit_meet_time(message):
    msg = bot.send_message(message.chat.id, "Введите ID встречи, которую хотите изменить:")
    bot.register_next_step_handler(msg, get_meet_id_for_edit)

def get_meet_id_for_edit(message):
    try:
        meet_id = int(message.text)
        msg = bot.send_message(message.chat.id, "Введите новое время встречи (формат ЧЧ:ММ):")
        bot.register_next_step_handler(msg, update_meet_time, meet_id)
    except Exception as ex:
        bot.send_message(message.chat.id, "Изменение времени прервано, но вы всегда можете начать заново!")

def update_meet_time(message, meet_id):
    new_time = message.text
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    
    cur.execute("UPDATE PlaneMeets SET time = ? WHERE id = ?", (new_time, meet_id))
    
    db.commit()
    db.close()
    bot.send_message(message.chat.id, f"Время встречи с ID {meet_id} было успешно изменено на {new_time}!")

@bot.message_handler(commands=['list_plane'])
@access_control
def list_plane(message):
    db = sqlite3.connect('stb_bot.db')
    cur = db.cursor()
    cur.execute("SELECT * FROM PlaneMeets")
    list_meets  = cur.fetchall()
    bot.send_message(message.chat.id, f"Все встречи:\n{list_meets}")
    db.close()

# Запуск функции send_prepared_info в отдельном потоке
thread1 = Thread(target=send_prepared_info)
thread1.start()

# Запуск функции send_start_notification в отдельном потоке
thread2 = Thread(target=send_start_notification)
thread2.start()

# Запуск бота
try:
    bot.polling()
except Exception as ex:
    print("Ошибка при запуске бота:", ex)
