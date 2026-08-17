"""管理端路由：账号管理（列表 / 创建 / 删除 / 重置密码），全部需管理员权限。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import PasswordResetRequest, UserCreateRequest, UserOut
from app.security import hash_password, require_admin

router = APIRouter(prefix="/api/admin/users", tags=["管理端-账号管理"])


@router.get("", response_model=list[UserOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """全部账号列表（不含密码哈希）。"""
    return db.query(User).order_by(User.id).all()


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """创建账号并分配角色（admin/user）。用户名重复 → 409。

    管理员账户仅可设置一个（当前为 admin）：已存在管理员时禁止再创建 admin 角色。
    """
    if db.query(User).filter(User.username == body.username).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    if body.role == "admin" and db.query(User).filter(User.role == "admin").first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="管理员账户仅可设置一个，系统已存在管理员")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """删除账号。禁止删除自己；审计日志保留（username 快照仍可读）。"""
    if user_id == admin.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="不能删除当前登录的账号")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    db.delete(user)
    db.commit()
    return {"detail": f"账号 {user.username} 已删除"}


@router.put("/{user_id}/password")
def reset_password(user_id: int, body: PasswordResetRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """重置指定账号的密码。"""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账号不存在")
    user.password_hash = hash_password(body.password)
    db.commit()
    return {"detail": f"账号 {user.username} 密码已重置"}
