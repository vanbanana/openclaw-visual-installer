# OpenClaw Qt6 Visual Installer (Windows / Linux)

现代化 Qt6 可视化安装器，用于把 OpenClaw 安装到“安全目录”，并在 GUI 中完成后续配置，不需要命令行交互。

## 特性
- Qt6 现代化桌面界面（深色主题、卡片布局、进度条、日志区）
- Windows / Linux 双平台
- 默认安全目录：`~/openclaw-safe`
- 安装命令使用 `npm --prefix <safeDir>/npm-prefix`
- 配置项全部在 GUI 中填写并写入
- 配置隔离：写入 `<safeDir>/state/openclaw.json`，不污染系统全局 OpenClaw
- 支持测试模式：`OPENCLAW_INSTALLER_TEST_MODE=1`

## 本地运行（源码）
```bash
python3 openclaw_installer_qt6.py
```

## Windows 发行版（EXE）
- Actions 工作流：`Build Windows EXE and Release`
- 手动触发后会发布：
  - `OpenClawInstaller-windows-x64.zip`
  - 内含 `OpenClawInstaller.exe`

## 测试
```bash
python3 -m pytest -q tests/test_openclaw_installer_gui.py
```

## 真实安装前置
- Node.js >= 18
- npm 可用

## 安装后 PATH
将下列目录加入 PATH：
- Linux/Windows: `<safeDir>/npm-prefix/node_modules/.bin`
