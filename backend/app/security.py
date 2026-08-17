"""安全模块：密码哈希（标准库 pbkdf2，零新增依赖）与 JWT 认证依赖。"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

# PBKDF2 参数
_PBKDF2_ITERATIONS = 600_000
_PBKDF2_SALT_BYTES = 16

# HTTP Bearer 认证方案（自动从 Authorization 头解析 token）
bearer_scheme = HTTPBearer(auto_error=False)


# ---------- 密码哈希 ----------

def hash_password(password: str) -> str:
    """生成密码哈希，格式：salt_hex$hash_hex。"""
    salt = secrets.token_bytes(_PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码（常量时间比较，防时序攻击）。"""
    try:
        salt_hex, hash_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest, expected)


# ---------- JWT ----------

def create_access_token(user: User) -> str:
    """签发 JWT：sub 为用户 id，过期时间由配置决定。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user.id), "username": user.username, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# ---------- FastAPI 依赖 ----------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """解析 Bearer token 并返回当前用户；未登录/无效/被禁用 → 401。"""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录，请先登录")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效，请重新登录")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不存在")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号已被禁用")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """管理员权限依赖：非 admin 角色一律 403。"""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限，仅管理员可执行此操作")
    return user
