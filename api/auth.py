"""
JWT 认证工具
使用 bcrypt 直接哈希，不依赖 passlib
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from api.config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_MINUTES


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(data: dict, expires_minutes: int) -> str:
    to_encode = data.copy()
    to_encode.update({
        "exp": datetime.now() + timedelta(minutes=expires_minutes),
        "iat": datetime.now(),
        "jti": secrets.token_hex(16),
    })
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: str) -> str:
    return create_token({"sub": user_id, "type": "access"}, ACCESS_TOKEN_EXPIRE_MINUTES)


def create_refresh_token(user_id: str) -> str:
    return create_token({"sub": user_id, "type": "refresh"}, REFRESH_TOKEN_EXPIRE_MINUTES)


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
