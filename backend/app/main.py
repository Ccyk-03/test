"""FastAPI 应用入口：CORS、路由挂载、启动建表与种子数据、SPA 静态服务。

启动方式：
- 开发模式（在 backend 目录下）：
    conda activate langchain
    uvicorn app.main:app --reload --port 8000
- 安装模式：由安装包快捷方式以 pythonw.exe 启动 run_app.pyw
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import app.runtime_env  # noqa: F401  导入即触发防拷贝安装校验（开发模式自动跳过）
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  导入以注册全部 ORM 模型
from app.database import Base, SessionLocal, engine
from app.routers import admin_audit, admin_config, admin_users, auth, conversations, units
from app.seed import seed_all

logging.basicConfig(level=logging.INFO)

# 前端构建产物目录：开发版 = GPT_Chat/frontend/dist；安装版 = $INSTDIR/frontend/dist
_DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用启动：建表 + 幂等写入种子数据（默认管理员、6 单元、s2）。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_all(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title="抽卡师的魔法",
    description="基于 LangChain 的链式递进提示词优化系统：管理界面 + 用户操作界面",
    version="1.0.0",
    lifespan=lifespan,
)

# 开发期前端走 Vite 代理，CORS 仅作兜底
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- API 路由（必须先于 SPA catch-all 注册）----
app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(units.router)
app.include_router(admin_users.router)
app.include_router(admin_audit.router)
app.include_router(admin_config.router)


@app.get("/api/health", tags=["系统"])
def health():
    """健康检查（启动验证 + 安装版自动开浏览器轮询）。"""
    return {"status": "ok"}


# ---- 前端 SPA 服务（打包模式：dist 存在时启用）----
# 注意：不能使用 app.mount("/", StaticFiles(html=True))，它会吞掉所有 /api 路由。
# 正确姿势：只挂载 /assets 静态子目录，再用 catch-all 路由回退到 index.html。
if (_DIST_DIR / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=_DIST_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """SPA 回退：dist 下的真实文件直接返回，其余（含 vue-router 深链）返回 index.html。"""
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="接口不存在")
        candidate = (_DIST_DIR / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_DIST_DIR.resolve()):
            return FileResponse(candidate)
        return FileResponse(_DIST_DIR / "index.html")
else:

    @app.get("/{full_path:path}", include_in_schema=False)
    def no_frontend(full_path: str):
        """开发模式：前端由 Vite(5173) 提供，此处仅提示。"""
        raise HTTPException(status_code=404, detail="前端未构建：开发模式请访问 http://localhost:5173，或先执行 npm run build")
