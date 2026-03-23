import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from database import db

# AES key must be exactly 32 bytes
RAW_KEY = os.environ.get("AES_SECRET_KEY", "MySuperSecretKey1234567890123456")
AES_KEY = RAW_KEY[:32].encode("utf-8")

def encrypt(plain_text: str) -> str:
    """Encrypt a string using AES-256 (CFB mode). Returns base64 string."""
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CFB(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(plain_text.encode()) + encryptor.finalize()
    # Store iv + encrypted together, base64 encoded
    return base64.b64encode(iv + encrypted).decode("utf-8")

def decrypt(cipher_text: str) -> str:
    """Decrypt a base64 AES-256 encrypted string."""
    raw = base64.b64decode(cipher_text.encode("utf-8"))
    iv = raw[:16]
    encrypted = raw[16:]
    cipher = Cipher(algorithms.AES(AES_KEY), modes.CFB(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    return (decryptor.update(encrypted) + decryptor.finalize()).decode("utf-8")


class Patient(db.Model):
    __tablename__ = "patients"

    id        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name      = db.Column(db.Text, nullable=False)   # stored encrypted
    age       = db.Column(db.Text, nullable=False)   # stored encrypted
    diagnosis = db.Column(db.Text, nullable=False)   # stored encrypted

    def set_data(self, name: str, age: str, diagnosis: str):
        """Encrypt and store patient fields."""
        self.name      = encrypt(name)
        self.age       = encrypt(age)
        self.diagnosis = encrypt(diagnosis)

    def get_data(self) -> dict:
        """Decrypt and return patient fields."""
        return {
            "id":        self.id,
            "name":      decrypt(self.name),
            "age":       decrypt(self.age),
            "diagnosis": decrypt(self.diagnosis),
        }