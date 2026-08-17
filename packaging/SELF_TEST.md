# Windows 实机自测清单（安装包验收）

在 Windows 机器上运行 `dist/PromptOpt-Setup-1.0.0.exe` 逐项验证。默认管理员：**admin / admin123**。

## 一、安装与启动

- [ ] 安装向导出现「模型服务商 / 模型名称 / 接口地址 / API Key」录入页，下拉切换服务商时接口地址与模型名自动填充
- [ ] 模型名称/接口地址已按打包时配置预填；可修改 API Key 后安装成功
- [ ] 桌面与开始菜单出现「提示词迭代优化系统」快捷方式
- [ ] 双击快捷方式：无黑色控制台窗口，几秒后浏览器自动打开 `http://127.0.0.1:8000` 登录页
- [ ] 再次双击快捷方式（服务已运行）：直接打开浏览器，不重复启动
- [ ] `%LOCALAPPDATA%\Programs\PromptOpt\` 下存在 runtime / backend / frontend / config.json / .installed
- [ ] `%APPDATA%\PromptOpt\app.db` 与 `logs\app.log` 已生成

## 二、环境变量与注册表（防拷贝机制）

- [ ] 新开 CMD 执行 `set P` → 可见 `PROMPT_OPT_INSTALLED=1` 与 `PROMPT_OPT_HOME=<安装目录>`
- [ ] `reg query HKCU\Environment` 可见两个变量；`reg query HKCU\Software\PromptOpt` 可见 InstallId
- [ ] **防拷贝测试**：将整个安装目录复制到 `C:\test\PromptOpt`，双击副本中
      `backend\run_app.pyw` → 弹窗「程序未通过安装校验」并退出
- [ ] 复制后手工 `setx PROMPT_OPT_INSTALLED 1` 再运行副本 → 仍被拦截（注册表因子）

## 三、核心功能回归（GPT 模型）

- [ ] admin/admin123 登录成功；普通账号登录成功；错误密码提示「用户名或密码错误」
- [ ] 用户端单元 1 输入分镜提示词 → 输出优化结果（结合 s1 指令），结果卡片显示「无基础模板」
- [ ] 单元 2 → 结果显示「链式来自单元 1」，输出体现空间连续性
- [ ] 单元 3-6 链式接续正常；「进入下一单元」「返回主界面」出口正常
- [ ] **修改流程**：单元 3 点「修改本单元」→ 对话框 1 自动预填 T2（可改）→ 对话框 2 输入需修改提示词
      → 输出新 T3，结果卡片显示「修改模式 · 结合 s3 指令」
- [ ] 修改单元 2 后再跑单元 3：链式基础模板是**修改后的 T2**
- [ ] 管理端审计：可见 optimize / revise 两类记录，来源含 none/chained/default/manual，
      点击行查看完整详情（输入输出/指令/基础模板/token/耗时）
- [ ] 管理端配置页：三份指令 s1/s2/s3 可编辑保存；6 单元默认模板可改；修改后用户端立即生效

## 四、LLM 模型配置（GPT 接口预留）

- [ ] 管理界面「模型配置」切换 provider 为 OpenAI GPT，填入模型名（自由填写）、
      接口地址（默认 `https://api.openai.com/v1`）、API Key → 保存
- [ ] 保存后 API Key 掩码显示（如 `sk-abc***wxyz`），无需重启
- [ ] 用户端执行优化 → 审计记录中模型名为所填 GPT 模型名

## 五、GPT 模型效果验证（取得 OpenAI Key 后执行）

> 前提：持有 OpenAI 官方或中转站 API Key。用户环境网络需能连通对应接口地址。

1. 管理界面「模型配置」：provider = OpenAI GPT，模型名 = `gpt-4o-mini`
   （或你 Key 可用的任意模型），base_url = 官方 `https://api.openai.com/v1` 或中转站地址，填 Key 保存
2. 用户端单元 1 输入示例分镜提示词：
   `镜头1：急救室内，Vincent站在病床边，手持除颤仪对患者进行电击，大喊：Charge to 200 joules! Clear!`
3. 预期：返回优化后的分镜提示词（含【分镜编号】【时间】【景别｜机位｜运镜】等结构）
4. 检查项（记录到交付报告）：
   - 输出结构规范性（十三、输出格式 的要素齐全度）
   - 情绪标签与可视化动作质量
   - 耗时与 token 用量（管理端审计详情可见）
   - 连续镜头链式效果（跑单元 1→2 看空间连续性）
5. 异常场景自测：
   - 错误 Key → 用户端报「模型调用失败」，管理端审计留痕 status=error
   - 网络不通 → 快速失败（max_retries=0），同上留痕
   - 企业网/代理：如遇 SSL 报错，在系统环境变量设置 `SSL_CERT_FILE` 指向企业 CA 证书，
     或配置 `HTTPS_PROXY` 后重启应用
6. 验证完成后可继续在管理界面更换模型 / 接口地址 / API Key（即时生效）

## 六、卸载

- [ ] 开始菜单「卸载」：确认提示 → 快捷方式/环境变量/注册表/安装目录全部清除
- [ ] `set P` 中两个变量消失；`reg query HKCU\Software\PromptOpt` 报找不到
- [ ] `%APPDATA%\PromptOpt` 数据保留（重新安装后历史数据仍在）
- [ ] 重新安装正常（.onInit 不再拦截）
