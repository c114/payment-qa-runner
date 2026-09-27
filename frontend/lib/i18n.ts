export type Locale = "zh" | "en";

const dict: Record<string, { zh: string; en: string }> = {
  appName: { zh: "Payment Test Runner", en: "Payment Test Runner" },
  home: { zh: "首页", en: "Home" },
  accounts: { zh: "账号", en: "Accounts" },
  testData: { zh: "测试数据", en: "Test Data" },
  runs: { zh: "运行记录", en: "Runs" },
  tasks: { zh: "任务", en: "Tasks" },
  settings: { zh: "设置", en: "Settings" },
  logout: { zh: "退出", en: "Logout" },
  helpBtn: { zh: "帮助", en: "Help" },
  help: { zh: "帮助", en: "Help" },
  start: { zh: "开始 START", en: "START" },
  stop: { zh: "停止 STOP", en: "STOP" },
  importAccounts: { zh: "导入账号", en: "Import Accounts" },
  selectAccounts: { zh: "选择账号", en: "Select Accounts" },
  importTestData: { zh: "导入测试数据", en: "Import Test Data" },
  liveBanner: { zh: "LIVE MODE — 真实 Chromium，无 Mock 回退", en: "LIVE MODE — real Chromium, no Mock fallback" },
};

export function t(locale: Locale, key: string): string {
  const row = dict[key];
  if (!row) return key;
  return row[locale] || row.zh || key;
}

export const mainNavItems = [
  { href: "/", key: "home" },
  { href: "/accounts", key: "accounts" },
  { href: "/test-data", key: "testData" },
  { href: "/runs", key: "runs" },
  { href: "/tasks", key: "tasks" },
  { href: "/settings", key: "settings" },
];
