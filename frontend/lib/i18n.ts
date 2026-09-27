export type Locale = "zh" | "en";

const dict = {
  zh: {
    appName: "Payment QA Runner",
    login: "登录",
    logout: "退出",
    startTest: "开始测试",
    results: "结果",
    reports: "报告",
    logs: "日志",
    help: "帮助",
    advanced: "高级设置",
    dashboard: "仪表盘",
    testRuns: "测试运行",
    testCases: "测试用例",
    txtImport: "TXT 导入",
    accounts: "QA 账号",
    proxies: "SOCKS5",
    sessions: "浏览器会话",
    environments: "环境",
    pageMapping: "页面映射",
    screenshots: "截图",
    settings: "系统设置",
    dataManagement: "数据管理",
    start: "开始",
    pause: "暂停",
    resume: "继续",
    stop: "停止",
    save: "保存",
    create: "创建",
    delete: "删除",
    test: "测试",
    helpBtn: "帮助",
    success: "成功",
    fail: "失败",
    error: "异常",
    mockBanner: "当前为 MOCK 模式 — 结果不是真实浏览器 PASS",
    importAccounts: "导入测试账号",
    selectTask: "选择任务",
    network: "网络",
    direct: "直连",
  },
  en: {
    appName: "Payment QA Runner",
    login: "Login",
    logout: "Logout",
    startTest: "Start Test",
    results: "Results",
    reports: "Reports",
    logs: "Logs",
    help: "Help",
    advanced: "Advanced",
    dashboard: "Dashboard",
    testRuns: "Test Runs",
    testCases: "Test Cases",
    txtImport: "TXT Import",
    accounts: "QA Accounts",
    proxies: "SOCKS5",
    sessions: "Browser Sessions",
    environments: "Environments",
    pageMapping: "Page Mapping",
    screenshots: "Screenshots",
    settings: "System Settings",
    dataManagement: "Data Management",
    start: "START",
    pause: "PAUSE",
    resume: "RESUME",
    stop: "STOP",
    save: "Save",
    create: "Create",
    delete: "Delete",
    test: "Test",
    helpBtn: "Help",
    success: "Success",
    fail: "Fail",
    error: "Error",
    mockBanner: "MOCK MODE — results are not live Chromium PASS",
    importAccounts: "Import accounts",
    selectTask: "Select task",
    network: "Network",
    direct: "Direct",
  },
} as const;

export type DictKey = keyof typeof dict.zh;

export function t(locale: Locale, key: DictKey): string {
  return dict[locale][key] || dict.zh[key];
}

/** Normal user menu */
export const mainNavItems: { href: string; key: DictKey }[] = [
  { href: "/", key: "startTest" },
  { href: "/results", key: "results" },
  { href: "/reports", key: "reports" },
  { href: "/logs", key: "logs" },
  { href: "/help", key: "help" },
];

/** Advanced settings (tech fields) */
export const advancedNavItems: { href: string; key: DictKey }[] = [
  { href: "/accounts", key: "accounts" },
  { href: "/proxies", key: "proxies" },
  { href: "/environments", key: "environments" },
  { href: "/page-mapping", key: "pageMapping" },
  { href: "/sessions", key: "sessions" },
  { href: "/cases", key: "testCases" },
  { href: "/runs", key: "testRuns" },
  { href: "/import", key: "txtImport" },
  { href: "/screenshots", key: "screenshots" },
  { href: "/settings", key: "settings" },
  { href: "/data-management", key: "dataManagement" },
];

/** @deprecated use mainNavItems + advancedNavItems */
export const navItems = [...mainNavItems, ...advancedNavItems];
