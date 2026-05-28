# Anything Codex Status

把一台能安装并登录 Tailscale 的 iOS 或 Android 闲置手机/平板，变成一块 Codex 监控屏。

它在运行 Codex 的电脑上启动一个轻量网页，读取本地 Codex 状态，然后通过 Tailscale 私有网络显示当前任务、账号、套餐、5h 额度、周额度和最近活动。iPhone、iPad、Android 手机、Android 平板都可以放在桌边，当作 Codex 的小副屏。

无论你的 Codex 安装在 macOS、Windows 还是 Linux，只要运行 Codex 的电脑和 iOS/Android 展示设备都能联网、都能安装并登录 Tailscale，就不需要处在同一个无线网络里。两端加入同一个 tailnet 后，你可以把手机或平板放在任意有网络的位置，用它查看 Codex 当前状态和额度。

[English](README-en.md) | 简体中文

> 开始前请先确认：你准备用作监控屏的 iOS 或 Android 手机/平板必须能安装并登录 Tailscale。不能安装或无法登录 Tailscale 的设备，不适合作为这个项目的展示设备。

[核心亮点](#核心亮点) • [功能说明](#功能说明) • [使用前提：需要 Tailscale](#使用前提需要-tailscale) • [用户必须操作的步骤](#用户必须手动操作的步骤) • [交给 Codex 安装](#交给-codex-安装) • [手动安装](#手动安装) • [部署为后台服务](#部署为后台服务) • [安全说明](#安全说明) • [开发与测试](#开发与测试)

---

## 核心亮点

Anything Codex Status 不是 Codex 的替代品，也不会接管你的任务。它只是把 Codex 已经写在本机的状态数据，整理成一个适合手机和平板横屏、竖屏查看的状态页。

- 闲置设备变监控屏：能安装 Tailscale 的 iPhone、iPad、Android 手机、Android 平板都可以用。
- 当前任务一眼可见：使用 Codex 左侧栏同款短标题，避免长 prompt 撑满页面。
- 额度实时展示：显示 5h 额度、周额度、重置倒计时和当前套餐。
- 桌宠状态气泡：跟随 Codex 桌面端当前选择的桌宠；官方内置桌宠从本机 Codex.app 运行时读取，自定义桌宠从 `~/.codex/pets` 读取。
- 隐私模式：关闭页面右上角 `Task` 开关后，只显示账号、套餐和额度，不显示任务内容。
- Tailscale 优先：展示设备和运行 Codex 的电脑加入同一个 tailnet 后，用电脑的 `100.x.y.z` 地址访问。
- Codex 可部署：新机器上把仓库链接交给 Codex，它可以边解释边检查环境，并协助部署。

---

## 功能说明

### 状态屏显示什么

- 登录账号：来自本机 Codex 账号缓存。
- 套餐：优先使用最新额度事件里的 plan 类型，例如 Pro。
- 5h 额度：来自 Codex 写入的 `rate_limits.primary`。
- 周额度：来自 Codex 写入的 `rate_limits.secondary`。
- 当前任务：优先使用 `session_index.jsonl` 里的左侧栏短标题。
- 最近请求：显示最近一次用户请求摘要。
- 最近活动：合并重复日志，显示工具调用、Codex 回复、额度采样等。
- 运行状态：根据最近用户消息、最终回复和最新事件判断 `RUNNING` / `READY`。
- 桌宠：读取 `~/.codex/config.toml` 的 `[desktop].selected-avatar-id`，优先显示 Codex 当前选择；官方内置 spritesheet 从已安装的 Codex.app 读取，自定义 spritesheet 从 `~/.codex/pets/<pet-id>/pet.json` 声明读取，并根据运行状态切换动画。

---

## 使用前提：需要 Tailscale

这个项目的前提是：运行 Codex 的电脑和用作监控屏的设备都能安装并登录 Tailscale。Tailscale 官方下载页列出 macOS、iOS、Windows、Linux、Android 客户端；[tailscale/tailscale](https://github.com/tailscale/tailscale) 仓库也说明核心 daemon 支持 Linux、Windows、macOS，并对 FreeBSD/OpenBSD 有不同程度支持。

- 运行 Codex 的电脑：可以是 macOS、Windows 或 Linux；它负责运行 Codex 和状态服务，并加入你的 Tailscale 网络。
- 闲置手机/平板：iOS 和 Android 都可以；安装 Tailscale，登录同一个账号或同一个 tailnet，然后用浏览器打开运行 Codex 电脑的 `100.x.y.z` 地址。
- 不能安装或不能登录 Tailscale 的设备，不作为这个项目的目标展示设备。

本机调试可以使用 `http://127.0.0.1:8765/`，但真正把手机或平板变成监控屏时，推荐只通过 Tailscale 私有网络访问。

---

## 用户必须手动操作的步骤

有些步骤 Codex 可以指导，但不能替你完成：

1. 登录 Codex：运行状态服务的电脑上必须已经登录并正常使用过 Codex。
2. 安装并登录 Tailscale：运行 Codex 的电脑和手机/平板都要加入同一个 Tailscale 网络。
3. 选择监控哪个项目：告诉 Codex 或命令行 `CODEX_STATUS_WORKSPACE` 应该指向哪个工作区。
4. 在手机/平板上打开 URL：Codex 可以给出地址，但需要你在展示设备的浏览器里打开。
5. 决定是否持久化：临时服务适合测试；后台服务会长期运行，必须由你明确同意。
6. 处理系统权限弹窗：如果系统防火墙询问是否允许 Python 接收入站连接，需要你手动允许。
7. 隐私选择：如果旁边有人或屏幕会外显，关闭页面右上角 `Task` 开关，只保留账号和额度信息。

---

## 交给 Codex 安装

在新机器上，推荐直接把 GitHub 仓库交给 Codex。你可以这样说：

> 适配性声明：本项目目前基于 macOS 开发和测试。如果你要在 Windows 或 Linux 上安装，请务必让 Codex 先检查路径、Python 命令、Codex 本地状态位置、防火墙和持久化方式是否适配当前系统。

```text
请阅读这个仓库并帮我把 Anything Codex Status 部署到这台运行 Codex 的电脑上：
https://github.com/ParkerGong/anything-codex-status

请先解释它会读取哪些本地 Codex 数据，再检查 Python、Codex 本地状态、Tailscale 和端口占用。
先启动临时服务，让我用 iOS/Android 手机或平板通过 Tailscale 测试。
只有我明确同意后，才做持久化部署；如果是 macOS 可以使用 LaunchAgent，如果是 Windows 或 Linux，请按当前系统选择合适的后台运行方式，并先告诉我会写入哪里、如何停止和移除。
```

如果仓库已经 clone 到本机，可以这样说：

```text
请阅读当前仓库，帮我部署 Codex 状态监控屏。
目标是让我的闲置手机或平板通过 Tailscale 打开状态页。
先临时启动服务，验证 /api/status，再告诉我本机 URL 和 Tailscale URL。
不要直接安装持久化服务；只有我确认测试可用并明确同意后，才继续配置后台运行。
如果我希望电脑重启后自动启动，或希望手机/平板可以持续访问状态页，请提醒我需要做持久化部署。
```

Codex 可以参考这些文件：

- [AGENTS.md](AGENTS.md)：给 Codex/agent 的部署规则。
- [docs/CODEX_INSTALL.md](docs/CODEX_INSTALL.md)：更细的部署手册。
- [codex-skill/anything-codex-status](codex-skill/anything-codex-status)：可选的 Codex skill。

---

## 手动安装

更推荐的方式仍然是把仓库链接交给 Codex，让它根据你的系统自动检查 Python、Codex 本地状态、Tailscale 和端口占用，再带着你部署。手动安装适合你想先理解每一步，或需要自己排查环境的时候使用。

### 1. 确认双端 Tailscale 前提

这个项目依赖外部组件 Tailscale。开始安装前，请先确认：

- 运行 Codex 的电脑可以安装并登录 Tailscale。
- 用作监控屏的 iOS/Android 手机或平板可以安装并登录 Tailscale。
- 两端加入同一个 Tailscale 网络后，手机/平板可以访问运行 Codex 电脑的 `100.x.y.z` 地址。

Tailscale 开源仓库：[tailscale/tailscale](https://github.com/tailscale/tailscale)

如果展示设备不能安装或不能登录 Tailscale，它就不适合作为这个项目的监控屏。

### 2. 克隆仓库

```bash
git clone https://github.com/ParkerGong/anything-codex-status.git
cd anything-codex-status
```

### 3. 检查环境

macOS / Linux：

```bash
python3 --version
test -d ~/.codex && echo "Codex state found"
test -f ~/.codex/state_5.sqlite && echo "state database found"
```

Windows PowerShell：

```powershell
python --version
Test-Path "$HOME\.codex"
Test-Path "$HOME\.codex\state_5.sqlite"
```

需要 Python 3.9+，并且这台电脑上已经登录和使用过 Codex。

### 4. 临时启动服务

把 `/path/to/workspace` 换成你希望监控的 Codex 项目目录：

macOS / Linux：

```bash
CODEX_STATUS_WORKSPACE="/path/to/workspace" \
CODEX_STATUS_PORT=8765 \
python3 -m anything_codex_status.server
```

如果只做本机开发验证，不希望临时服务监听 Tailscale 或局域网地址，可以额外指定：

```bash
CODEX_STATUS_HOST=127.0.0.1
```

Windows PowerShell：

```powershell
$env:CODEX_STATUS_WORKSPACE="C:\path\to\workspace"
$env:CODEX_STATUS_PORT="8765"
python -m anything_codex_status.server
```

本机打开：

```text
http://127.0.0.1:8765/
```

检查接口：

```bash
curl http://127.0.0.1:8765/api/status
```

### 5. 手机或平板打开

先确认运行 Codex 的电脑和手机/平板都已经安装并登录 Tailscale，然后在电脑上找 `100.x.y.z` 地址：

优先使用 Tailscale 自带命令，macOS / Windows / Linux 都适用：

```bash
tailscale ip -4
```

如果 macOS / Linux 上没有 `tailscale` 命令，也可以尝试：

```bash
ifconfig | grep '100\.'
```

手机或平板浏览器打开：

```text
http://<mac-tailscale-ip>:8765/
```

例如：

```text
http://100.x.y.z:8765/
```

---

## 部署为后台服务

临时服务只适合测试或短时间使用。若你希望电脑重启或重新登录后自动启动状态页，或者希望手机/平板可以长期持续访问，就需要做持久化部署。

确认手机/平板能访问、并且你接受隐私风险后，可以安装为 macOS LaunchAgent。

```bash
python3 scripts/install_launch_agent.py \
  --workspace "/path/to/workspace" \
  --port 8765 \
  --load
```

它会写入：

```text
~/Library/LaunchAgents/io.github.anything-codex-status.plist
```

检查状态：

```bash
launchctl print gui/$(id -u)/io.github.anything-codex-status
lsof -nP -iTCP:8765 -sTCP:LISTEN
curl http://127.0.0.1:8765/api/status
```

停止并移除：

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/io.github.anything-codex-status.plist
rm ~/Library/LaunchAgents/io.github.anything-codex-status.plist
```

---

## 安装可选 Codex Skill

如果你希望以后直接对 Codex 说“修一下状态屏”或“重新启动状态屏”，可以安装仓库自带的 skill：

```bash
mkdir -p ~/.codex/skills/anything-codex-status
cp -R codex-skill/anything-codex-status/* ~/.codex/skills/anything-codex-status/
```

之后可以问 Codex：

```text
Use $anything-codex-status to start or repair my Codex phone/tablet status dashboard.
```

---

## 安全说明

这个项目只读取本机文件，不主动上传数据，也不会调用 OpenAI API。

会读取的典型文件包括：

- `~/.codex/state_5.sqlite`
- `~/.codex/goals_1.sqlite`
- `~/.codex/session_index.jsonl`
- `~/.codex/accounts/registry.json`
- `~/.codex/config.toml`
- `~/.codex/pets/*/pet.json`
- `~/.codex/pets/*/spritesheet.webp`
- `/Applications/Codex.app/Contents/Resources/app.asar` 中的官方桌宠 spritesheet
- 当前会话的 `rollout-*.jsonl`

请注意：

- 状态页没有登录认证。
- 不建议暴露到公网。
- 推荐只在 localhost 或 Tailscale 私有网络里使用。
- 页面可能显示账号邮箱、本机路径、任务标题、prompt 摘要和额度信息。
- 如果启用 `Pet` 开关，页面会显示本机 Codex pet 动画；关闭 `Task` 开关时，桌宠气泡也会隐藏任务文本。
- 浏览器每 3 秒刷新一次 `/api/status`，这不会消耗 Codex token，只会产生很轻的本机文件读取和网络流量。

---

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 标准库 `http.server` + `sqlite3` |
| 前端 | 单文件 HTML / CSS / JavaScript |
| 数据来源 | Codex 本地状态与 rollout 日志 |
| 部署 | 临时命令或 macOS LaunchAgent |
| 远程访问 | Tailscale |

---

## 开发与测试

运行检查：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/anything-codex-status-pycache \
python3 -m py_compile \
  server.py \
  anything_codex_status/server.py \
  scripts/install_launch_agent.py \
  codex-skill/anything-codex-status/scripts/codex_status_server.py \
  codex-skill/anything-codex-status/scripts/install_launch_agent.py \
  tests/test_server.py

PYTHONPYCACHEPREFIX=/private/tmp/anything-codex-status-pycache \
python3 -m unittest discover -s tests
```

如果修改了 `anything_codex_status/server.py`，请同步 skill 里的服务器脚本：

```bash
cp anything_codex_status/server.py codex-skill/anything-codex-status/scripts/codex_status_server.py
```

---

## 许可证

MIT License
