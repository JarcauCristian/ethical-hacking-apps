from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)

def hash_password(password):
    return pwd_context.hash(password)

