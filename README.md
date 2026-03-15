# OpenClaw 可视化一键安装器（Windows / Linux）

这是一个基于 Tkinter 的本地 GUI 小应用，用于把 OpenClaw 安装到“安全目录”，避免污染系统全局环境。

## 特性
- 可视化一键安装（美观三步界面：安装/配置/日志）
- Windows / Linux 双平台
- 默认安全目录：`~/openclaw-safe`
- 安装命令使用 `npm --prefix <safeDir>/npm-prefix`
- 后续配置全部在 GUI 内填写并一键写入（无需命令行交互）
- 配置写入使用隔离环境：`<safeDir>/state/openclaw.json`，不污染当前系统 OpenClaw
- 支持测试模式：`OPENCLAW_INSTALLER_TEST_MODE=1`（不联网、不改系统）

## 运行
```bash
python3 openclaw_installer_gui.py
```

## 测试（已通过）
```bash
python3 -m pytest -q tests/test_openclaw_installer_gui.py
```

## 测试模式说明
```bash
OPENCLAW_INSTALLER_TEST_MODE=1 python3 openclaw_installer_gui.py
```
测试模式会创建 fake `openclaw` 可执行文件，验证流程与目录隔离，不会执行真实安装。

## 真实安装前置
- Node.js >= 18
- npm 可用

## 安装后
将下列目录加入 PATH：
- Linux: `<safeDir>/npm-prefix/bin`
- Windows: `<safeDir>/npm-prefix`
