# 安装包构建手册

产物：**Windows 安装程序 `dist/PromptOpt-Setup-<版本>.exe`**（NSIS 安装包，内嵌 Python 3.12 运行时，免管理员权限）。

## 一、构建前置（WSL / Linux 内完成，无需 Windows 侧 Python）

| 工具 | 用途 | 检查命令 |
|---|---|---|
| makensis（NSIS ≥ 3） | 编译 Windows 安装包 | `makensis -VERSION` |
| curl / unzip / sha256sum | 下载并校验 Python 运行时 | 系统自带 |
| node / npm | 构建前端 | `node --version` |
| conda 环境 `langchain` 的 pip | 下载 win_amd64 依赖 wheel | 已配置 |

```bash
sudo apt install nsis curl unzip   # 如缺少 nsis
```

## 二、一键构建

```bash
cd /home/cyk/python_Project/GPT_Chat/packaging
./build.sh                 # 默认版本 1.0.0
PRODUCT_VERSION=1.0.1 ./build.sh   # 指定版本号
```

构建流程（8 步，每步有明确失败提示）：

1. 前置工具检查
2. `npm run build` 构建前端
3. 下载 Python 3.12.10 embeddable（哈希固化校验，可复用缓存）
4. 解压运行时并修补 `python312._pth`（启用 `import site` + `Lib\site-packages`）
5. `pip download --platform win_amd64 --python-version 3.12 --only-binary=:all:` 下载依赖
   ——`--only-binary` 让「无 Windows wheel 的包」在构建期快速失败
6. 解包全部 wheel 到 `runtime/Lib/site-packages`
   ——说明：`pip install --target` 不接受跨平台 wheel，wheel 本质是 zip 归档，
   直接解包（跳过 .data 目录）即可满足运行时导入需求
7. 组装安装布局（backend 排除 data/source/__pycache__；frontend/dist；runtime）
8. `makensis` 编译 → `dist/PromptOpt-Setup-<版本>.exe` + SHA256

> 备选：若 pip 的跨平台 wheel 解析遇到环境标记问题（pip issue #11664），
> 可改用 `uv pip install --python-platform x86_64-pc-windows-msvc --python 3.12 --target ...`。

## 三、安装行为（用户侧）

- 默认安装目录：`%LOCALAPPDATA%\Programs\PromptOpt`（免 UAC，可改路径）
- 安装向导第 3 页：录入**模型名称 / 接口地址 / API Key**（写入安装目录 `config.json`）；
  模型固定为 OpenAI GPT，向导默认值来自打包时读取的开发期模型配置
  （更换模型/Key 后打包，交付的安装程序即带该配置；Key 在向导密码框以掩码显示）
- 安装器写入**用户环境变量**（防拷贝机制第一因子）：
  - `PROMPT_OPT_INSTALLED = 1`
  - `PROMPT_OPT_HOME = <安装目录>`
- 同时写入注册表 `HKCU\Software\PromptOpt\InstallId` 与安装目录 `.installed` 标记（第二/第三因子）
- 桌面 + 开始菜单快捷方式（pythonw.exe 启动 `backend/run_app.pyw`，无控制台窗口，
  启动后自动打开浏览器 `http://127.0.0.1:8000`）
- 数据目录：`%APPDATA%\PromptOpt`（app.db + logs，卸载时保留）

## 四、防拷贝机制说明

程序启动时（`backend/app/runtime_env.py` 的 guard，任何启动方式均触发）校验：

1. 环境变量 `PROMPT_OPT_INSTALLED == "1"`
2. `PROMPT_OPT_HOME` 指向安装目录，且程序运行路径位于安装目录之内
3. 注册表 `InstallId` 与安装目录 `.installed` 标记文件一致

任一失败 → 弹窗报错退出。**直接拷贝文件夹到其他位置/机器 → 无法运行。**

如实说明：该机制防「普通拷贝」，对有意技术破解（手工伪造全部标记）不设防；
如需更强防护需机器指纹/代码签名/联网激活，超出本项目定位。

## 五、卸载

开始菜单「卸载」或「设置 → 应用」：删除快捷方式、环境变量、注册表与安装目录；
用户数据（`%APPDATA%\PromptOpt`）保留，如不需要请手动删除。

## 六、常见问题

- **SmartScreen 拦截**：未签名 exe 首次运行可能提示 → 「更多信息 → 仍要运行」；
  正式分发建议代码签名（可选后续工作）
- **8000 端口被占用**：run_app.pyw 会预检端口；若检测到本程序已在运行则直接打开浏览器；
  其他程序占用时请改端口（改 `run_app.pyw` 的 APP_PORT 后重新打包）
- **启动失败**：查看 `%APPDATA%\PromptOpt\logs\app.log`（pythonw 无控制台，日志全在文件里）
