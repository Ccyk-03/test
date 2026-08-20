; ============================================================
; 抽卡师的魔法 - NSIS 安装脚本
; 编译（WSL 内）：makensis -DPRODUCT_VERSION=1.0.0 -DINPUT_STAGING=build/staging installer.nsi
; 安装布局：$LOCALAPPDATA\Programs\PromptOpt（免管理员权限）
; 无防拷贝校验：仅写入 .installed 安装标记（用于程序判断安装版路径）
; ============================================================
Unicode true
!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "winmessages.nsh"
!include "FileFunc.nsh"

!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "1.0.0"
!endif
!ifndef INPUT_STAGING
  !define INPUT_STAGING "build\staging"
!endif

Name "抽卡师的魔法"
OutFile "dist\PromptOpt-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$LOCALAPPDATA\Programs\PromptOpt"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show

!define APP_REG_KEY "Software\PromptOpt"

; ---------------- 页面流 ----------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
; 安装完成后自动运行应用（pythonw 无控制台窗口）
; 注意：本版 MUI2 会将 RUN 用 $\" 包裹，PARAMETERS 原样追加到 Exec 字符串中，
; 因此 PARAMETERS 内的引号必须写成 $\"（否则 Exec 收到多个参数而报错）
!define MUI_FINISHPAGE_RUN "$INSTDIR\runtime\pythonw.exe"
!define MUI_FINISHPAGE_RUN_PARAMETERS '$\"$INSTDIR\backend\run_app.pyw$\"'
!define MUI_FINISHPAGE_RUN_TEXT "立即运行抽卡师的魔法"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

; ---------------- 变量 ----------------

; ============================================================
; 安装
; ============================================================
Section "Install"
  SetOutPath "$INSTDIR"

  ; 1. 拷贝运行时 / 后端 / 前端
  File /r "${INPUT_STAGING}\runtime"
  File /r "${INPUT_STAGING}\backend"
  File /r "${INPUT_STAGING}\frontend"

  ; 2. 写入安装标记文件（用于程序判断「安装版」路径，不做防拷贝校验）
  FileOpen $7 "$INSTDIR\.installed" w
  FileWrite $7 '{"installed":true}'
  FileClose $7

  ; 5. 快捷方式（pythonw.exe 无控制台窗口启动；起始目录设为 backend）
  SetOutPath "$INSTDIR\backend"
  CreateShortcut "$DESKTOP\抽卡师的魔法.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\backend\run_app.pyw"'
  CreateDirectory "$SMPROGRAMS\抽卡师的魔法"
  CreateShortcut "$SMPROGRAMS\抽卡师的魔法\抽卡师的魔法.lnk" "$INSTDIR\runtime\pythonw.exe" '"$INSTDIR\backend\run_app.pyw"'
  CreateShortcut "$SMPROGRAMS\抽卡师的魔法\卸载.lnk" "$INSTDIR\Uninstall.exe"

  ; 6. 卸载信息
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "DisplayName" "抽卡师的魔法"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "Publisher" "PromptOpt"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "NoRepair" 1

  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; ============================================================
; 卸载
; ============================================================
Section "Uninstall"
  MessageBox MB_OKCANCEL|MB_ICONINFORMATION "如程序正在运行，请先关闭后再卸载。$\r$\n$\r$\n用户数据（数据库与日志，位于 %APPDATA%\PromptOpt）将保留。继续卸载？" IDOK +2
    Abort

  Delete "$DESKTOP\抽卡师的魔法.lnk"
  RMDir /r "$SMPROGRAMS\抽卡师的魔法"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt"

  RMDir /r "$INSTDIR"

  MessageBox MB_ICONINFORMATION "卸载完成。$\r$\n用户数据保留在 %APPDATA%\PromptOpt，如不再需要请手动删除。"
SectionEnd

; ============================================================
; 初始化：检测重复安装 + 初始化模型变量（静默安装 /S 时页面被跳过，仍写入正确配置）
; ============================================================
Function .onInit
  ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\PromptOpt" "InstallLocation"
  ${If} $0 != ""
    MessageBox MB_ICONEXCLAMATION "检测到本系统已安装。请先通过开始菜单「卸载」或「设置 → 应用」卸载后重新安装。"
    Abort
  ${EndIf}
FunctionEnd
