# OpenClaw 可视化一键安装器（Windows / Linux）

本项目提供本地 GUI（Tkinter）安装器，目标是把 **OpenClaw 首次可用前的关键决策点全部图形化**，避免“能装上但不会配”。

## P0 可视化覆盖（硬门槛）

1. **运行模式选择**
   - 本地 / 远程 Gateway
   - bind: loopback/lan/tailnet/custom
   - auth: none/token/password/trusted-proxy

2. **模型与 API 配置**
   - Provider 选择
   - API Key 输入 + 格式校验按钮
   - 默认模型、thinking、verbose

3. **Skills 选择与安装**
   - 推荐技能包（可多选）
   - 安装前显示来源/版本/风险

4. **Hooks 可视化配置**
   - 模板选择（webhook/gmail/custom）
   - 触发条件与路由目标
   - 启用开关 + 测试按钮

5. **权限模式**
   - reply-only / allowlist / full
   - full 模式二次确认弹窗
   - 当前生效权限状态可见

6. **Gateway Token 与 Dashboard**
   - 一键生成 / 刷新 token
   - 一键复制 token
   - 一键打开 Dashboard
   - token 有效状态显示

7. **首次对话前完整检查**
   - 一键检查 environment/model/skills/hooks/permission/gateway/dashboard

## 运行

```bash
python3 openclaw_installer_gui.py
```

## 测试

```bash
python3 -m pytest -q tests/test_openclaw_installer_gui.py
```

## 测试模式

```bash
OPENCLAW_INSTALLER_TEST_MODE=1 python3 openclaw_installer_gui.py
```

测试模式不联网，不执行真实安装/配置写入，适合本地快速验收 GUI 流程。

## 发行版 EXE 打包

### 本地（Windows）

```bash
bash scripts/build_windows_exe.sh
```

产物：`release/OpenClawInstaller.exe`

### CI（推荐）

已提供 GitHub Actions：`.github/workflows/release-installer-exe.yml`
- 手动触发：`workflow_dispatch`
- 或打 tag：`installer-v*`
- 产物：Artifacts 中的 `OpenClawInstaller-exe`

> 说明：Linux 环境无法原生产出可运行的 Windows EXE，需在 Windows Runner 执行打包。

## 安装后 PATH 提示

安装路径默认：`~/openclaw-safe`。

可执行目录提示：`<safeDir>/npm-prefix/node_modules/.bin`
