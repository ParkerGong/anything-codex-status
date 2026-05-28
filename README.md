# Anything Codex Status

把你的闲置手机、平板、Kindle 浏览器或任意带浏览器的设备，变成一块 Codex 监控屏。

它在 Mac 本机启动一个轻量网页，读取本地 Codex 状态，然后通过局域网或 Tailscale 显示当前任务、账号、套餐、5h 额度、周额度和最近活动。适合把旧 iPhone / iPad / Android 平板放在桌边，当作 Codex 的小副屏。

[English](README-en.md) | 简体中文

核心亮点 • 功能说明 • 交给 Codex 安装 • 手动安装 • 用户必须操作的步骤 • 部署为后台服务 • 安全说明 • 开发与测试

---

## 核心亮点

Anything Codex Status 不是 Codex 的替代品，也不会接管你的任务。它只是把 Codex 已经写在本机的状态数据，整理成一个适合手机横屏、竖屏和轻量浏览器查看的状态页。

- 闲置设备变监控屏：旧手机、平板、Kindle 浏览器都可以用。
- 当前任务一眼可见：使用 Codex 左侧栏同款短标题，避免长 prompt 撑满页面。
- 额度实时展示：显示 5h 额度、周额度、重置倒计时和当前套餐。
- 隐私模式：关闭页面右上角 `Task` 开关后，只显示账号、套餐和额度，不显示任务内容。
- Tailscale 友好：校园网、公司 Wi-Fi、同网段不可直连时，也可以用 Tailscale 私有 IP 访问。
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

### 额度怎么更新

网页每 3 秒请求一次本机的 `/api/status`。这个请求只读本地文件，不调用模型，不消耗 token。

服务会读取当前 Codex 会话的 rollout 日志：

```text
~/.codex/sessions/.../rollout-*.jsonl
```

Codex 在对话和执行任务时会写入 `token_count` 事件。页面读取最新一条 `token_count`：

- `rate_limits.primary` 显示为 5h 额度。
- `rate_limits.secondary` 显示为周额度。
- `rate_limits.plan_type` 用来校正套餐显示。

如果长时间没有新的 `token_count`，额度百分比可能暂时保持旧值；重置倒计时会随着页面刷新重新计算。

---

## 交给 Codex 安装

在新机器上，推荐直接把 GitHub 仓库交给 Codex。你可以这样说：

```text
请阅读这个仓库并帮我把 Anything Codex Status 部署到这台 Mac 上：
<GITHUB_REPO_URL>

请先解释它会读取哪些本地 Codex 数据，再检查 Python、Codex 本地状态和 Tailscale。
先启动临时服务让我用手机测试；只有我明确同意后，才安装 LaunchAgent 后台服务。
```

如果仓库已经 clone 到本机，可以这样说：

```text
请阅读当前仓库，帮我部署 Codex 状态监控屏。
目标是让我的闲置手机或平板通过 Tailscale 打开状态页。
先临时启动服务，验证 /api/status，再告诉我本机 URL 和 Tailscale URL。
```

Codex 可以参考这些文件：

- [AGENTS.md](AGENTS.md)：给 Codex/agent 的部署规则。
- [docs/CODEX_INSTALL.md](docs/CODEX_INSTALL.md)：更细的部署手册。
- [codex-skill/anything-codex-status](codex-skill/anything-codex-status)：可选的 Codex skill。

---

## 手动安装

### 1. 克隆仓库

```bash
git clone <GITHUB_REPO_URL>
cd anything-codex-status
```

### 2. 检查环境

```bash
python3 --version
test -d ~/.codex && echo "Codex state found"
test -f ~/.codex/state_5.sqlite && echo "state database found"
```

需要 Python 3.9+，并且这台机器上已经登录和使用过 Codex。

### 3. 临时启动服务

把 `/path/to/workspace` 换成你希望监控的 Codex 项目目录：

```bash
CODEX_STATUS_WORKSPACE="/path/to/workspace" \
CODEX_STATUS_PORT=8765 \
python3 -m anything_codex_status.server
```

本机打开：

```text
http://127.0.0.1:8765/
```

检查接口：

```bash
curl http://127.0.0.1:8765/api/status
```

### 4. 手机或平板打开

如果 Mac 和手机在同一可互通网络，可以打开：

```text
http://<mac-lan-ip>:8765/
```

如果同一 Wi-Fi 不能互通，推荐使用 Tailscale。

先在 Mac 和手机上都登录 Tailscale，然后在 Mac 上找 `100.x.y.z` 地址：

```bash
ifconfig | grep '100\.'
```

手机浏览器打开：

```text
http://<mac-tailscale-ip>:8765/
```

例如：

```text
http://100.x.y.z:8765/
```

---

## 用户必须手动操作的步骤

有些步骤 Codex 可以指导，但不能替你完成：

1. 登录 Codex：目标 Mac 上必须已经登录并正常使用过 Codex。
2. 安装并登录 Tailscale：Mac 和手机/平板都要加入同一个 Tailscale 网络。
3. 选择监控哪个项目：告诉 Codex 或命令行 `CODEX_STATUS_WORKSPACE` 应该指向哪个工作区。
4. 在手机上打开 URL：Codex 可以给出地址，但需要你在手机浏览器里打开。
5. 决定是否持久化：临时服务适合测试；后台 LaunchAgent 会长期运行，必须由你明确同意。
6. 处理系统权限弹窗：如果 macOS 防火墙询问是否允许 Python 接收入站连接，需要你手动允许。
7. 隐私选择：如果旁边有人或屏幕会外显，关闭页面右上角 `Task` 开关，只保留账号和额度信息。

---

## 部署为后台服务

确认手机能访问、并且你接受隐私风险后，可以安装为 macOS LaunchAgent。

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
Use $anything-codex-status to start or repair my Codex phone status dashboard.
```

---

## 安全说明

这个项目只读取本机文件，不主动上传数据，也不会调用 OpenAI API。

会读取的典型文件包括：

- `~/.codex/state_5.sqlite`
- `~/.codex/goals_1.sqlite`
- `~/.codex/session_index.jsonl`
- `~/.codex/accounts/registry.json`
- 当前会话的 `rollout-*.jsonl`

请注意：

- 状态页没有登录认证。
- 不建议暴露到公网。
- 推荐只在 localhost、可信局域网或 Tailscale 私有网络里使用。
- 页面可能显示账号邮箱、本机路径、任务标题、prompt 摘要和额度信息。
- 浏览器每 3 秒刷新一次 `/api/status`，这不会消耗 Codex token，只会产生很轻的本机文件读取和网络流量。

---

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 标准库 `http.server` + `sqlite3` |
| 前端 | 单文件 HTML / CSS / JavaScript |
| 数据来源 | Codex 本地状态与 rollout 日志 |
| 部署 | 临时命令或 macOS LaunchAgent |
| 远程访问 | Tailscale / 私有局域网 |

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
