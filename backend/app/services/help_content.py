"""Help Center content (zh/en) per page."""
from __future__ import annotations

HELP = {
    "dashboard": {
        "zh": "仪表盘显示实时统计与配置向导（1–11 步）。完成环境、映射、账号、用例后即可 START 运行。",
        "en": "Dashboard shows live stats and setup wizard steps 1–11. Configure env, mappings, accounts, cases, then START.",
    },
    "environments": {
        "zh": "仅配置 Sandbox/Staging/Internal QA 的 Base URL，并设置 allowed_domains。浏览器 Worker 会拒绝导航到白名单外域名。不要把正式站 preply.com 设为默认生产支付环境。",
        "en": "Configure Sandbox/Staging/Internal QA Base URLs with allowed_domains. Worker refuses navigation outside allowlist. Preply.com is UI reference only.",
    },
    "page-mapping": {
        "zh": "对照 docs/screenshots/page-1.png … page-7.png 编辑选择器。支持 CSS / 文本 / Playwright locator / iframe。Test Selector 仅定位元素，不发起支付。",
        "en": "Edit selectors against screenshots pages 1–7. Supports CSS/text/Playwright/iframe. Test Selector locates only — no payment.",
    },
    "accounts": {
        "zh": "QA 密码加密存储。账号自动创建默认关闭；启用时必须设置非 gmail/outlook/yahoo 的测试邮箱域名。",
        "en": "QA passwords encrypted at rest. Account auto-creation OFF by default; requires non-consumer test email domain.",
    },
    "proxies": {
        "zh": "SOCKS5 池。禁止从互联网抓取代理。仅 NETWORK_ERROR/PROXY_DOWN/CONNECTION_TIMEOUT 时可自动切换 Network Profile；CARD_DECLINED/3DS 等禁止轮换。",
        "en": "SOCKS5 pool. No scraping proxies. Auto-switch Network Profile only on NETWORK_ERROR/PROXY_DOWN/CONNECTION_TIMEOUT.",
    },
    "test-cases": {
        "zh": "PASS/FAIL = Expected vs Actual。期望 DECLINED 且实际 DECLINED = PASS。检测到 3DS → Actual=3DS, Status=FAIL（若期望非 3DS），立即结束用例，不求解 OTP。CVV 永不落库。",
        "en": "PASS/FAIL compares Expected vs Actual. 3DS → FAIL (unless expected), end case, never solve OTP. Never persist CVV.",
    },
    "payrails": {
        "zh": "系统设置 → Payrails 面板。沙箱字段默认留空，由管理员填写。勿编造 API 密钥。",
        "en": "System Settings → Payrails panel. Sandbox fields blank by default — admin fills. Never invent API secrets.",
    },
    "runner": {
        "zh": "默认间隔 5s、超时 30s、网络重试 2、超时重试 1、拒付重试 0。账号连续失败达阈值后冷却并切换下一 READY 账号。每 N 用例或 PAGE_ERROR/BROWSER_CRASH/NETWORK_ERROR 时重启浏览器。",
        "en": "Defaults: interval 5s, timeout 30s, network retry 2, timeout retry 1, decline retry 0.",
    },
    "default": {
        "zh": "Payment QA Runner — 沙箱支付自动化 QA 工具。详见 Help Center。",
        "en": "Payment QA Runner — sandbox payment automation QA tool.",
    },
}


def get_help(page_key: str) -> dict:
    return HELP.get(page_key, HELP["default"]) | {"page": page_key}
