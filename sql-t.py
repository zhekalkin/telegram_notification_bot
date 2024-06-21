import sqlite3
db = sqlite3.connect('stb_bot.db')
cur = db.cursor()
# cur.execute("INSERT INTO chat (id_chat) VALUES (-1002155719308);")
# cur.execute("INSERT INTO white_list (chat_id, name) VALUES (6704458870, 'Evgeniy');")
# cur.execute("CREATE TABLE chat (id_chat INTERGER PRIMARY KEY)")
# cur.execute("CREATE TABLE CanceledMeetings (id INTEGER PRIMARY KEY AUTOINCREMENT,   meet_id INTEGER,   cancel_date TEXT);")
db.commit()
meets = cur.fetchall()
print(meets)
db.close()

#перед использованием бота, добавьте свой chat_id в БД в таблицу white_list, иначе бот будет отклонять все запросы
