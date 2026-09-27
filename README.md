# Payment Test Runner

**Version 2.0.0** — 导入账号 → 导入测试数据 → 选任务/网络 → START → 真实 Chromium → SUCCESS/FAIL/ERROR → 导出/清理。

仓库：https://github.com/c114/payment-qa-runner

> 不是通用 QA 平台 / 工作流编辑器 / Page Mapping / Case 管理器。

---

## 用户流程

1. 打开面板 `http://SERVER_IP:3000` 并登录
2. **账号**：粘贴 `email|password` 或 `email----password` → 预览 → 确认导入 → 选择
3. **测试数据**（Sandbox 绑卡任务需要）：`卡号|MM/YY|CVC` → 预览 → 确认（列表仅掩码，无 CVC）
4. **首页**：选 Task、选 Network（默认 Direct）→ 就绪检查全过 → **START**
5. **运行记录**：实时进度 / SUCCESS·FAIL·ERROR / 日志 / 截图·Trace → 导出 TXT/CSV → 清理

主导航：**首页 | 账号 | 测试数据 | 运行记录 | 任务 | 设置**

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

## 内置任务

| 任务 | 环境 | 说明 |
|------|------|------|
| **Preply Payment Page Smoke** | Production | 登录 + Payment methods + Add card **检测**。**禁止**真实填卡/提交 |
| **Local Sandbox Card Binding** | Sandbox | 对 Docker `sandbox:8080` 完整 Login→Fill→Submit→Parse |

---

## 结果码

`SUCCESS/BOUND` · `FAIL/DECLINED` · `FAIL/3DS_REQUIRED` · `FAIL/INVALID_DATA` ·  
`ERROR/BAD_CREDENTIALS` · `ERROR/LOGIN_TIMEOUT` · `ERROR/NETWORK_ERROR` ·  
`ERROR/TARGET_NOT_FOUND` · `ERROR/BROWSER_ERROR` · `ERROR/UNKNOWN_RESULT`

未知结果 **永不** 映射为 SUCCESS。

---

## 架构

| 服务 | 说明 |
|------|------|
| frontend | Next.js :3000 |
| backend | FastAPI :8000 |
| worker | Playwright Chromium（始终 LIVE） |
| sandbox | 本地绑卡模拟器 :8080（内部） |

DB：SQLite + Alembic（2.0 全新 schema，无 1.x 兼容）。无 Redis/Kafka。

---

## 安全

- Mode 始终 **LIVE**；无 Live→Mock 回退
- Production 禁止填卡提交
- 密码 Fernet 加密；列表/日志/导出永不含密码或 CVC
- 3DS：立即 FAIL/3DS_REQUIRED，截图+trace，继续下一项
- 仅 NETWORK_ERROR 有限重试；无验证码/登录封锁 IP 轮换

---

## 开发

```bash
# 后端测试
cd backend && pytest -v

# 前端
cd frontend && npm run build

# Compose
docker compose build && docker compose up -d
docker compose ps
curl -s http://127.0.0.1:8000/api/health
```

详见 `TASK_SPEC.md` / `TASK_STATE.md`。
