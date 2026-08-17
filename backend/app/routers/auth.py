"""认证路由：登录、当前用户信息。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    """账号密码登录，成功签发 JWT。统一错误提示，不泄露账号是否存在。"""
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号已被禁用")
    return LoginResponse(access_token=create_access_token(user), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    """返回当前登录用户信息（前端刷新页面时恢复登录态用）。"""
    return user
