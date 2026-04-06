from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

# We try to get the existing key from the env, if not found, we generate one.
# It is important to save it so that data isn't lost on restart if .env isn't set.
env_key = os.environ.get('CHAVE_CRIPTOGRAFIA')

if not env_key:
    # Generates a valid fernet key
    env_key = Fernet.generate_key().decode('utf-8')
    print(f"ATENÇÃO: 'CHAVE_CRIPTOGRAFIA' não encontrada no ambiente. Usando chave efêmera de fallback: {env_key}")

cipher = Fernet(env_key.encode('utf-8'))

def crypt_field(data: str) -> str:
    if not data:
        return data
    return cipher.encrypt(str(data).encode('utf-8')).decode('utf-8')

def decrypt_field(data_hash: str) -> str:
    if not data_hash:
        return data_hash
    try:
        return cipher.decrypt(data_hash.encode('utf-8')).decode('utf-8')
    except Exception:
        # Fallback to plain text mostly for backward compatibility
        return data_hash
