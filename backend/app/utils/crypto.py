from cryptography.fernet import Fernet
from ..config import settings

class CryptoUtil:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.fernet = Fernet(settings.ENCRYPTION_KEY)
        return cls._instance
    
    def encrypt_id(self, project_id: str) -> str:
        if not project_id:
            raise ValueError("Project ID cannot be empty")
        return self.fernet.encrypt(str(project_id).encode()).decode()
        
    def decrypt_id(self, encrypted_id: str) -> str:
        return self.fernet.decrypt(encrypted_id.encode()).decode() 