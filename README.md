# Payment QA Runner

**Version 1.3.0** — 一键浏览器 QA 自动化 Runner。普通用户：导入账号 → 选任务 → 点开始；真实 Chromium 跑冒烟/沙箱测试。

仓库：**Public** https://github.com/c114/payment-qa-runner

---

## 普通用户流程（推荐）

1. 打开面板 `http://SERVER_IP:3000` 并登录
2. **开始测试**：粘贴 `email|password` 或 `email----password` 导入账号
3. 选择管理员预置任务（如 *Preply Payment Page Smoke Test* 或 *本地浏览器冒烟*）
4. 点击 **开始 START**
5. 查看进度 / 成功 / 失败 / 异常、实时日志、截图与报告

普通用户**无需**配置选择器、Page Mapping、Environment、Browser Session、Workflow JSON、Network Profile 技术字段、Test Case 技术字段。这些在侧边栏 **高级设置** 中。

---

## Quick Start

```bash
curl -fsSL https://raw.githubusercontent.com/c114/payment-qa-runner/main/install.sh | sudo bash
```

或：

```bash
git clone https://github.com/c114/payment-qa-runner.git /opt/payment-qa-runner
cd /opt/payment-qa-runner && sudo bash install.sh
```

更新：

```bash
cd /opt/payment-qa-runner && sudo bash update.sh
```

面板：`http://SERVER_IP:3000`（Same-Origin：`/api/*` 由 Next 代理到 backend）  
调试 API：`http://SERVER_IP:8000/api/health`

---

## 任务类型

| 任务 | 说明 |
|------|------|
| **Preply Payment Page Smoke Test** | 生产 **UI Smoke ONLY**：登录 → Payment methods → Add card（可选弹窗）。**不填卡号/CVV/提交** |
| **Local Chromium Smoke (fixture)** | 本地 HTML 夹具，无需 Preply 账号，用于证明真实 Chromium |
| **Authorized Sandbox Payment Test** | 沙箱填卡占位；需 `LIVE_TESTING_ENABLED=true` + sandbox\|staging\|internal |

---

## Mock vs Live

| 模式 | 何时 | 行为 |
|------|------|------|
| **LIVE**（默认） | `PLAYWRIGHT_MOCK=0` | 真实 Playwright/Chromium；无浏览器则不能 PASS |
| **MOCK** | `PLAYWRIGHT_MOCK=1` / CI / 管理端显式 Mock | 模拟结果；前端显示 **MOCK MODE** 横幅；不与 live PASS 混用 |

**已删除** `Live testing refused → force mock`。拒绝实时时返回错误码：`LIVE_TESTING_DISABLED`、`ENVIRONMENT_NOT_ALLOWED` 等。

生产 Smoke（不填卡）在 `LIVE_TESTING_ENABLED=false` 时仍可跑真实浏览器。填卡工作流必须 `LIVE_TESTING_ENABLED` + 非 production。

---

## 安全规则

- 生产 Preply：仅 UI Smoke；禁止卡号/CVV 填写提交
- CAPTCHA / LOGIN_BLOCKED / BAD_CREDENTIALS：**不**轮换 IP
- 仅 `NETWORK_ERROR` / `CONNECTION_TIMEOUT` / `PROXY_DOWN` 可自动网络重试
- 无自动注册；缺账号 → `ACCOUNT_NOT_READY`
- CVV 仅内存，不落库/日志/报告；PAN 掩码
- Session：`data/sessions/account_{id}.json`（gitignore）

---

## 架构

- Frontend：Next.js standalone（`node server.js`），Same-Origin API（`api.ts` 空 base → `/api/...`）
- Backend：FastAPI + SQLite（或 Postgres profile）
- Worker：Playwright Chromium，DB 轮询队列；截图 + `trace.zip`
- `docs/` 纳入版本库（含 `docs/fixtures/local-smoke.html`），保证 `COPY docs` 可用

---

## 常用命令

```bash
sudo bash install.sh
sudo bash update.sh      # 先备份；不删 .env/data；冲突文件进 backups/local-changes-<ts>/
sudo bash status.sh
sudo bash diagnose.sh
sudo bash repair.sh
sudo bash logs.sh
sudo bash restart.sh
sudo bash backup.sh
sudo bash restore.sh backups/<file>.tgz
```

默认环境：`PLAYWRIGHT_MOCK=0`；不要设置 `NEXT_PUBLIC_API_URL=http://localhost:8000`。

---

## 开发

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
mkdir -p data/{screenshots,reports,logs,sessions}
cd backend && pytest -q
cd ../frontend && npm install && npm run lint && npm run build
```

健康检查示例：

```bash
curl -s http://127.0.0.1:8000/api/health
# {"mode":"LIVE"|"MOCK","version":"1.3.0", ...}
```
