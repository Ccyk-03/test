# 提示词迭代优化系统（影视分镜提示词优化）

基于 **LangChain** 的链式递进提示词优化平台，分为「管理界面」与「用户操作界面」两个操作端口，支持打包为 Windows 安装程序交付。

**业务场景**：影视分镜提示词优化——6 个优化单元对应 6 个连续镜头（对话），每个单元输入当前镜头的分镜提示词 tᵢ，输出适用于 AI 视频生成的优化提示词 Tᵢ；链式机制保证人物动作与空间关系的镜头间连续性。

## 一、系统架构

```
浏览器 (Vue 3 + Element Plus)
   │  开发期 :5173（Vite 代理）；打包后由 FastAPI 直接服务 SPA（:8000）
   ▼
FastAPI
   ├── 认证（pbkdf2 密码哈希 + JWT，两级角色 admin/user）
   ├── 用户端：6 单元概览 / 执行优化 / 修改提示词（revise）/ 单元历史
   ├── 管理端：账号管理 / 审计查询 / 单元配置 / 三指令配置 / 模型配置（GPT 接口）
   └── LangChain LCEL 链（init_chat_model → OpenAI GPT，模型名自由填写）
SQLite（开发 backend/data/app.db；安装版 %APPDATA%\PromptOpt\app.db）
LangSmith（.env 已开启，每次调用自动追踪）
```

## 二、核心机制

### 对话流程（链式递进优化）

| 对话 | 调用指令 | 基础模板 | 说明 |
|---|---|---|---|
| 单元 1（首次对话） | **s1**（指令s1.doc） | 无 | 用户提示词 t₁ + s1 → T₁ |
| 单元 2 | **s1**（指令s1.doc） | 自动链式 T₁ | t₂ + s1 + 链式基础模板 → T₂ |
| 单元 i（≥3，后续对话） | **s2**（指令s2.docx） | 自动链式 Tᵢ₋₁ | tᵢ + s2 + 链式基础模板 → Tᵢ；无历史回退单元默认模板 |
| 修改对话 i | **s3**（s3指令.docx） | 手动输入 Tᵢ₋₁ | 见下方修改流程 |

- 每轮调用 = 基础模板 + 调用指令（s1/s2/s3）+ 单元指令（管理端配置 + 用户本次追加）+ tᵢ。
- 链式规则：单元 i 自动取「当前用户最近一次单元 i-1 的成功输出」为基础模板。
- 每次调用（成功或失败）写入审计日志：账号、单元号、操作类型（优化/修改）、输入输出、
  生效指令、基础模板来源与快照、模型名、token 用量、耗时、时间戳。

### 修改流程（revise）

已生成对话 1-6 后，点击任一单元「✏️ 修改本单元提示词」：
1. **对话框 1**：输入上一次生成的最终提示词（自动预填 Tᵢ₋₁，可修改）——作为基础模板；
2. **对话框 2**：输入需要修改的提示词；
3. 系统结合 **s3 指令** 重新生成新的 Tᵢ；修改后的 Tᵢ 自动接续链式关系，
   之后运行单元 i+1 会以修改后的 Tᵢ 为基础模板。

### 三份调用指令

原始文档位于 `backend/app/source/`（指令s1.doc / 指令s2.docx / s3指令.docx），
已全文内嵌为种子数据，管理端「优化单元配置」页可随时编辑：
- **s1**：单元 1、2 指令（专业影视分镜优化指令体）
- **s2**：单元 3-6 统一调用指令（链式衔接句 + 专业指令体）
- **s3**：修改提示词指令（手动衔接句 + 专业指令体；原文档中「手动粘贴上一镜头结果」
  已由修改对话框的输入承接）

### LLM 模型配置（GPT 接口预留）

- 仅支持 **OpenAI GPT**（官方 / OpenRouter 等 OpenAI 兼容端点）；模型名自由填写
- 安装版：安装向导录入（写入安装目录 config.json）；开发版：管理界面「模型配置」录入
  （写入 backend/config.json）；API Key 只显示掩码、不明文展示
- 保存后立即生效（自动清模型单例缓存，无需重启）；API Key 掩码展示
- GPT 效果验证步骤见 `packaging/SELF_TEST.md` 第五节

## 三、两个操作端口

| | 管理界面 | 用户操作界面 |
|---|---|---|
| 入口 | 主界面「管理界面」卡片（仅 admin） | 主界面「用户操作界面」卡片 |
| 登录 | 账号密码 → JWT | 账号密码 → JWT |
| 功能 | ① 账号管理（创建/删除/重置密码、两级角色）<br>② 审计查询（按账号/单元/操作/状态/时间筛选）<br>③ 配置 6 个优化单元<br>④ 编辑三份指令 s1/s2/s3<br>⑤ 模型配置（GPT 接口） | 6 个优化单元（链式进度条）<br>每单元：tᵢ 输入 / 自定义指令面板 / 执行优化 / ✏️修改本单元<br>修改两段式对话框 + 历史回看 |
| 操作出口 | 侧边栏「返回系统主界面」 | 「返回系统主界面」/「进入下一流程层级」 |

## 四、目录结构

```
GPT_Chat/
├── backend/                  # FastAPI 后端
│   ├── requirements.txt
│   ├── data/app.db           # 开发版 SQLite（运行时生成）
│   ├── run_app.pyw           # 安装版启动入口（pythonw 无控制台 + 自动开浏览器）
│   └── app/
│       ├── main.py           # 入口：guard、CORS、路由、SPA 服务、建表播种
│       ├── config.py         # 配置（.env / 安装版 config.json 的 JWT 密钥）
│       ├── runtime_env.py    # 安装/开发双模式路径 + 防拷贝三重校验 guard
│       ├── model_config.py   # LLM 模型配置（provider/模型/Key/base_url）
│       ├── database.py       # SQLAlchemy 引擎与会话
│       ├── models.py         # users / audit_logs / unit_configs / global_config
│       ├── schemas.py        # Pydantic 请求/响应模型
│       ├── security.py       # pbkdf2 密码哈希 + JWT + 角色依赖
│       ├── seed.py           # 种子数据（admin、6 单元、s1/s2/s3 全文）
│       ├── llm_service.py    # init_chat_model + 三层/两层指令 Prompt + LCEL 链
│       ├── chain_state.py    # 链式基础模板解析 + 三指令读取
│       ├── source/           # 原始需求文档（指令s1/s2/s3）
│       └── routers/          # auth / units / admin_users / admin_audit / admin_config
├── frontend/                 # Vue 3 + Vite 前端（api / stores / router / views）
└── packaging/                # 安装包构建（交付化）
    ├── build.sh              # 一键构建 → dist/PromptOpt-Setup-<版本>.exe
    ├── installer.nsi         # NSIS 脚本（模型配置向导页/环境变量/防拷贝标记/卸载器）
    ├── requirements-win.txt  # Windows 运行时依赖（cp312 win_amd64 wheel 已验证）
    ├── README.md             # 构建手册
    └── SELF_TEST.md          # Windows 实机自测清单 + GPT 验证大纲
```

## 五、启动方式

### 开发模式

```bash
# 后端（端口 8000）
conda activate langchain
cd /home/cyk/python_Project/GPT_Chat/backend
uvicorn app.main:app --reload --port 8000

# 前端（端口 5173，浏览器访问 http://localhost:5173）
cd /home/cyk/python_Project/GPT_Chat/frontend
npm install && npm run dev
```

**默认管理员：admin / admin123**（登录后可在管理界面创建普通用户账号）。

### 打包安装（Windows 交付）

```bash
cd /home/cyk/python_Project/GPT_Chat/packaging
./build.sh   # WSL 内一键构建 Windows 安装包（详见 packaging/README.md）
```

安装后双击快捷方式 → 自动打开浏览器使用；只有通过安装包安装的程序才能运行
（环境变量 + 注册表 + 安装标记三重校验，拷贝文件夹无法运行）。

## 六、主要 API

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | /api/auth/login | 公开 | 登录，签发 JWT |
| GET | /api/auth/me | 登录 | 当前用户信息 |
| GET | /api/units | 登录 | 6 单元概览（链式进度） |
| POST | /api/units/{n}/run | 登录 | 执行优化（s1/s2 + 链式 + 审计） |
| POST | /api/units/{n}/revise | 登录 | 修改提示词（s3 + 手动基础模板 + 审计） |
| GET | /api/units/{n}/history | 登录 | 当前用户该单元历史 |
| GET/POST | /api/admin/users | admin | 账号列表 / 创建 |
| DELETE | /api/admin/users/{id} | admin | 删除账号（审计保留） |
| PUT | /api/admin/users/{id}/password | admin | 重置密码 |
| GET | /api/admin/audit | admin | 审计分页筛选（含 action 筛选） |
| GET | /api/admin/audit/{id} | admin | 审计完整详情 |
| GET/PUT | /api/admin/units[/{n}] | admin | 单元配置读写 |
| GET/PUT | /api/admin/global | admin | 三份指令 s1/s2/s3 读写 |
| GET/PUT | /api/admin/model | admin | LLM 模型配置（GPT 接口） |

交互式 API 文档：http://localhost:8000/docs

## 七、验收清单（对照需求）

- [x] 管理员账号密码登录鉴权；普通用户登录后才能使用优化功能
- [x] 管理端账号管理：创建/删除/重置密码、两级角色授权
- [x] 管理端审计：按账号查询使用历史（优化/修改、来源、token、耗时全字段）
- [x] 管理端配置 6 组优化单元与三份调用指令 s1/s2/s3
- [x] 用户端 6 组优化单元：tᵢ 输入 → Tᵢ 输出 → 自定义指令面板
- [x] 单元 1、2 结合 s1；后续对话（单元 3-6）结合 s2 + 自动链式 Tᵢ₋₁
- [x] 修改流程：两段式对话框（上一次最终提示词 + 需修改提示词）+ s3 指令，修改结果接续链条
- [x] 审计记录账号/操作类型/输入输出/指令/来源/token/耗时/时间戳
- [x] 两个操作出口：返回系统主界面、进入下一流程层级
- [x] LangSmith 全链路追踪
- [x] Windows 安装包（内嵌 Python 运行时 + 安装向导录入模型配置）
- [x] 防拷贝：环境变量 + 注册表 + 安装标记三重校验，拷贝文件夹无法运行
- [x] GPT 模型接口预留（provider 切换 + 模型名自由填写 + 自测大纲）
