# Payment QA Runner

**Version 1.2.0** — 沙箱 / Staging / Internal QA 支付流程自动化工具。通过 Playwright 按 Page Mapping 与 Workflow 执行加卡流程，对比 **Expected vs Actual** 判定 PASS/FAIL。  
**Preply.com 仅作 UI 参考**（`docs/screenshots/`），默认不连接正式站。Payrails 密钥由管理员在面板填写，仓库不包含伪造密钥。

仓库现为 **Public**：https://github.com/c114/payment-qa-runner

---

## Quick Start (Public)

### One-shot install

```bash
curl -fsSL https://raw.githubusercontent.com/c114/payment-qa-runner/main/install.sh | sudo bash
```

### Or clone then install

```bash
git clone https://github.com/c114/payment-qa-runner.git /opt/payment-qa-runner
cd /opt/payment-qa-runner
sudo bash install.sh
```

### Quick Commands

```bash
sudo bash install.sh     # 首次安装（自动装 Docker、生成 secrets、compose up）
sudo bash update.sh      # 备份 → pull → build → restart → health
sudo bash status.sh      # 状态 / health
sudo bash diagnose.sh    # 版本 / commit / Docker / 容器 / 磁盘 / 日志
sudo bash repair.sh      # 修复目录权限 / 重启
sudo bash logs.sh        # 日志（可跟 backend|worker|frontend）
sudo bash restart.sh     # 重启
sudo bash backup.sh      # 备份
sudo bash restore.sh backups/<file>.tgz
```

面板：**`http://SERVER_IP:3000`**（浏览器只访问 3000；`/api/*` 由 Next.js 同源代理到 backend）  
API 调试口：`http://SERVER_IP:8000`（可选）

**Same-Origin（1.2.0）**：无需配置 `NEXT_PUBLIC_API_URL` / 公网 CORS IP。`install.sh` 一键成功。

---
## 功能概览

- 管理端：Dashboard、Environments（Clone/Import/Export）、Page Mapping（CRUD/JSON/Test Selector）、Workflow、QA Accounts（批量导入导出）、SOCKS5（批量/Test All/Export）、Network Profiles、Browser Sessions（全动作）、Test Cases（批量）、统一导入中心、Test Runs、Results、Screenshots、Reports、Logs、System Settings（含 Payrails）、Help
- **Same-Origin API（1.2.0）**：浏览器只访问 `:3000`；Next.js `app/api/[...path]` 代理到 `backend:8000`，无需 `NEXT_PUBLIC_API_URL` / 公网 CORS
- Worker：异步 Playwright（`PLAYWRIGHT_MOCK=1` 可无真实浏览器跑 CI）
- 安全：域名白名单、CVV 不落库、PAN 掩码 `**** **** **** 1234`、密码/代理密码 Fernet 加密、拒付/3DS **禁止**自动换代理

## 硬性安全规则（代码强制）

| 规则 | 行为 |
|------|------|
| 环境 | 仅 sandbox / staging / internal；`allowed_domains` 白名单，Worker 拒绝域外导航 |
| 代理轮换 | **仅** `NETWORK_ERROR` / `PROXY_DOWN` / `CONNECTION_TIMEOUT` 可自动切换 Network Profile |
| 禁止轮换 | `CARD_DECLINED` / `RISK_BLOCK` / `TOO_MANY_ATTEMPTS` / `INVALID_*` / `3DS` 等 |
| 3DS | Actual=`3DS`，与 Expected 比较后 FAIL（除非 Expected 也是 3DS），立即结束用例，不求解 OTP |
| PASS/FAIL | Expected == Actual → PASS（如 DECLINED+DECLINED） |
| CVV | 仅内存填充，提交后丢弃；报告/日志/DB 不含 CVV |
| 账号自动创建 | 默认 OFF；启用需非 gmail/outlook/yahoo 测试域名 |

---

## 本地开发

### 依赖

- Python 3.11+、Node 20+、（可选）Docker

### 后端 + Worker

```bash
cd payment-qa-runner
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env   # 编辑 ADMIN_* / JWT_SECRET / ENCRYPTION_KEY
mkdir -p data/screenshots data/reports data/logs

export PYTHONPATH="$PWD/backend:$PWD"
export DATABASE_URL="sqlite:////$PWD/data/payment_qa.db"
export PLAYWRIGHT_MOCK=1   # 本地无支付站时用 mock

# 终端 1
uvicorn app.main:app --app-dir backend --reload --port 8000

# 终端 2
python -m worker.runner
```

健康检查：`curl http://localhost:8000/api/health`

### 前端

```bash
cd frontend
npm install
export NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
# http://localhost:3000
```

默认管理员：`.env` 中 `ADMIN_EMAIL` / `ADMIN_PASSWORD`（首次启动写入哈希）。

### 测试

```bash
source .venv/bin/activate
export PYTHONPATH="$PWD/backend:$PWD" PLAYWRIGHT_MOCK=1 JWT_SECRET=test
cd backend && pytest tests/ -v
cd ../frontend && npm run build
```

---

## Docker / VPS

```bash
cp .env.example .env
# 生成密钥后：
./deploy.sh
```

`deploy.sh`：检查 Docker、补全密钥、建目录、`docker compose up -d --build`、健康检查。  
可选 Postgres：`docker compose --profile postgres up -d` 并设置 `DATABASE_URL=postgresql+psycopg2://qa:qa@postgres:5432/payment_qa`。

| 脚本 | 作用 |
|------|------|
| `./deploy.sh` | 首次部署 |
| `./update.sh` | 拉取/构建/迁移/重启；失败提示 rollback |
| `./backup.sh` | 备份 `data/`（及 `.env`） |
| `./restore.sh backups/xxx.tgz` | 恢复 |

容器卷：`./data`、`./screenshots`、`./logs`、`./reports`。

---

## 管理员登录与配置向导

1. 打开前端 → 登录  
2. Dashboard 向导 1–11：环境 → 映射 → 账号 → 用例 → Payrails → Runner → 创建 Run → START  
3. **Environments**：填写沙箱 Base URL + `allowed_domains`（勿把正式 preply.com 当默认生产支付环境）  
4. **Page Mapping**：按下方教程改选择器，可用 Test Selector（只定位）  
5. **System Settings → Payrails**：填写沙箱 URL / merchant / 选择器 / `sandbox_cards`（管理员自备 sandbox 卡数据）  
6. **TXT 导入**：见 `examples/`  
7. **Test Runs**：选环境/账号/网络/用例数 `1|5|10|50|ALL` → START / PAUSE / RESUME / STOP  

---

## Preply UI 映射教程（截图 page-1 … page-7）

截图目录：`docs/screenshots/`。种子数据带 **示例**选择器（`is_example=true`），必须按你的沙箱修改。

| 页 | 截图 | 映射 key | 操作 |
|----|------|----------|------|
| 1 | page-1.png | `home.login_btn` | 首页 → Log In |
| 2 | page-2.png | `login.signup_student_link` 等 | 登录层 / Sign up as a student |
| 3 | page-3.png | `signup.*` / `login.*` | 注册表单或登录 |
| 4 | page-4.png | `nav.user_menu`, `nav.settings_link` | 用户菜单 → Settings |
| 5 | page-5.png | `settings.payment_methods` | 侧栏 Payment methods |
| 6 | page-6.png | `payment.add_card_btn` | Add card |
| 7 | page-7.png | `payment.payrails_iframe`, `payment.card_*`, `payment.save_btn` | Save a payment card（常为 Payrails iframe） |

选择器类型：`css` / `text` / `playwright` / iframe（`iframe_selector` + 内部 selector）。

---

## Payrails 面板位置

前端：**系统设置 → Payrails 配置面板**  
API：`GET/PUT /api/payrails-config`  
字段默认留空；`api_key` 加密存储；`sandbox_cards` 按 `payment_test_ref` 提供填表用卡号（CVV 仅用于当次填充）。

---

## 导入样例

见 `examples/qa_accounts.txt`、`examples/socks5.txt`、`examples/test_cases.txt`。  
用例默认列：`case_id|name|payment_test_ref|expected_result|card_brand|pan_last4|expiry`（CVV 列忽略）。

---

## Browser Sessions

操作：open / restart_page / restart_browser / clear_cookies / re_login / switch_account / **switch_network** / close。  
`switch_network` = **新建 browser context**，不热补丁代理。默认 Max Concurrent Browsers = 1。

## Runner

默认：间隔 5s、超时 30s、网络重试 2、超时重试 1、**拒付重试 0**。  
账号连续失败达阈值 → 冷却 → 切换下一 READY。  
每 N 用例或 PAGE_ERROR / BROWSER_CRASH / NETWORK_ERROR 重启浏览器。  
截图策略默认：`FAIL,ERROR,3DS`。

## Results / Reports

结果含步骤时间线；导出 CSV / XLSX / JSON / HTML（无 secrets / 完整 PAN / CVV）。

---


## Caddy / HTTPS (optional)

Example file: `deploy/Caddyfile.example` (preferred — Caddy is **not** forced into `docker-compose.yml`).

**With domain** (`DOMAIN=qa.example.com`, DNS A/AAAA → server):
- Automatic HTTPS
- `https://qa.example.com` → frontend `:3000`
- `https://qa.example.com/api` → backend `:8000`
- Set `NEXT_PUBLIC_API_URL=https://qa.example.com` (or empty for same-origin `/api`) at frontend build time

**Without domain**:
- `http://SERVER_IP:3000` (frontend) and `http://SERVER_IP:8000` (API)
- Or host Caddy on `:80` reverse-proxying both (see commented Option B in the example)

Preflight: `./scripts/vps-preflight.sh`

SQLite: backend + worker share `./data` → `sqlite:////data/payment_qa.db`.  
Postgres profile requires changing `DATABASE_URL` — do not leave conflicting sqlite defaults.

## 故障排查

| 现象 | 处理 |
|------|------|
| `/api/health` worker=false | 确认 worker 进程与同一 `DATABASE_URL`；SQLite 建议 WAL |
| 导航被拒 | 检查 Environment `allowed_domains` |
| 选择器找不到 | Page Mapping + Test Selector；对照截图 |
| 3DS 全 FAIL | 预期行为；或 Expected 设为 `3DS` |
| Docker 不可用 | 使用本地 venv + npm 方式 |
| bcrypt 警告 | passlib 与 bcrypt 4.x 兼容警告，可忽略 |

---

## 目录结构

```
payment-qa-runner/
  backend/          FastAPI + SQLAlchemy + Alembic
  worker/           Playwright 消费者
  frontend/         Next.js 15 App Router
  examples/         TXT 样例
  docs/screenshots/ UI 参考
  docker-compose.yml
  deploy.sh update.sh backup.sh restore.sh
  README.md ACCEPTANCE.md FINAL-ACCEPTANCE.md
  deploy/Caddyfile.example
  scripts/vps-preflight.sh
```

## License

Internal QA tool — 仅限授权沙箱环境使用。
