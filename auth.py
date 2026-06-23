import os
import warnings
import bcrypt as _bcrypt
from datetime import datetime, timedelta
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
# Supports either a bcrypt hash (starts with $2b$) or a plain-text password.
# Plain-text is accepted for backwards compatibility but will log a warning.
# To upgrade: set ADMIN_PASSWORD to the output of:
#   python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def authenticate_admin(username: str, password: str) -> bool:
    if username != ADMIN_USERNAME:
        return False
    # Secure path: ADMIN_PASSWORD is a bcrypt hash
    if ADMIN_PASSWORD.startswith("$2b$") or ADMIN_PASSWORD.startswith("$2a$"):
        return verify_password(password, ADMIN_PASSWORD)
    # Legacy plain-text fallback — warn loudly
    warnings.warn(
        "ADMIN_PASSWORD is stored as plain text. "
        "Upgrade it: set ADMIN_PASSWORD to the output of: "
        "python -c \"import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())\"",
        stacklevel=2,
    )
    return password == ADMIN_PASSWORD


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username != ADMIN_USERNAME:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username

