"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function SettingsPage() {
  const [runner, setRunner] = useState<any>(null);
  const [payrails, setPayrails] = useState<any>(null);
  const [apiKey, setApiKey] = useState("");
  const [msg, setMsg] = useState("");
  const [resultMapText, setResultMapText] = useState("{}");
  const [threedsText, setThreedsText] = useState("[]");
  const [cardsText, setCardsText] = useState("{}");

  useEffect(() => {
    api("/runner-settings").then(setRunner);
    api("/payrails-config").then((p) => {
      setPayrails(p);
      setResultMapText(JSON.stringify(p.result_selectors || {}, null, 2));
      setThreedsText(JSON.stringify(p.threeds_selectors || [], null, 2));
      // Never expect decrypted api_key — only has_api_key
      const cards = { ...(p.sandbox_cards || {}) };
      setCardsText(JSON.stringify(cards, null, 2));
    });
  }, []);

  if (!runner || !payrails) return <p className="text-surface-muted">加载中...</p>;

  return (
    <div className="space-y-4">
      <div className="card space-y-2">
        <h2 className="font-semibold">Runner 设置</h2>
        <p className="help-field">decline_retry 固定为 0（禁止因拒付轮换代理）。截图策略默认 FAIL,ERROR,3DS。</p>
        <div className="grid md:grid-cols-3 gap-2">
          {(["interval_sec", "timeout_sec", "network_retry", "timeout_retry", "account_failure_threshold", "account_cooldown_sec", "restart_browser_every_n", "max_concurrent_browsers"] as const).map((k) => (
            <label key={k} className="text-xs block">
              {k}
              <input className="w-full mt-1" type="number" value={runner[k]} onChange={(e) => setRunner({ ...runner, [k]: Number(e.target.value) })} />
            </label>
          ))}
          <label className="text-xs block md:col-span-2">
            screenshot_policy
            <input className="w-full mt-1" value={runner.screenshot_policy} onChange={(e) => setRunner({ ...runner, screenshot_policy: e.target.value })} />
          </label>
        </div>
        <button className="btn" onClick={async () => {
          try {
            setRunner(await api("/runner-settings", { method: "PUT", body: JSON.stringify({ ...runner, decline_retry: 0 }) }));
            setMsg("Runner 已保存");
          } catch (e: any) { setMsg(e.message); }
        }}>保存 Runner</button>
      </div>

      <div className="card space-y-2">
        <h2 className="font-semibold">Payrails 配置面板</h2>
        <p className="help-field">
          沙箱 URL / merchant / project、test reference（sandbox_cards）、success/declined/3DS 映射选择器。
          API Key 仅写入：响应只含 has_api_key={String(!!payrails.has_api_key)}，从不回传明文密钥。
        </p>
        <div className="grid md:grid-cols-2 gap-2">
          <input placeholder="sandbox_base_url" value={payrails.sandbox_base_url || ""} onChange={(e) => setPayrails({ ...payrails, sandbox_base_url: e.target.value })} />
          <input placeholder="merchant_id / project" value={payrails.merchant_id || ""} onChange={(e) => setPayrails({ ...payrails, merchant_id: e.target.value })} />
          <input placeholder="public_key" value={payrails.public_key || ""} onChange={(e) => setPayrails({ ...payrails, public_key: e.target.value })} />
          <input type="password" placeholder={payrails.has_api_key ? "API Key (已设置，留空保持)" : "API Key (blank)"} value={apiKey} onChange={(e) => setApiKey(e.target.value)} autoComplete="new-password" />
          <input placeholder="iframe_selector" value={payrails.iframe_selector || ""} onChange={(e) => setPayrails({ ...payrails, iframe_selector: e.target.value })} />
          <input placeholder="card_number_selector" value={payrails.card_number_selector || ""} onChange={(e) => setPayrails({ ...payrails, card_number_selector: e.target.value })} />
          <input placeholder="expiry_selector" value={payrails.expiry_selector || ""} onChange={(e) => setPayrails({ ...payrails, expiry_selector: e.target.value })} />
          <input placeholder="cvv_selector" value={payrails.cvv_selector || ""} onChange={(e) => setPayrails({ ...payrails, cvv_selector: e.target.value })} />
          <input placeholder="submit_selector" value={payrails.submit_selector || ""} onChange={(e) => setPayrails({ ...payrails, submit_selector: e.target.value })} />
          <label className="text-xs md:col-span-2 block">
            result_selectors JSON（success / declined / 3DS 等映射）
            <textarea className="w-full mt-1 font-mono text-xs" rows={4} value={resultMapText} onChange={(e) => setResultMapText(e.target.value)} />
          </label>
          <label className="text-xs md:col-span-2 block">
            threeds_selectors JSON array
            <textarea className="w-full mt-1 font-mono text-xs" rows={2} value={threedsText} onChange={(e) => setThreedsText(e.target.value)} />
          </label>
          <label className="text-xs md:col-span-2 block">
            sandbox_cards JSON（test reference → 填表数据；CVV 仅沙箱）
            <textarea className="w-full mt-1 font-mono text-xs" rows={4} value={cardsText} onChange={(e) => setCardsText(e.target.value)} />
          </label>
          <textarea className="md:col-span-2" placeholder="notes" value={payrails.notes || ""} onChange={(e) => setPayrails({ ...payrails, notes: e.target.value })} />
        </div>
        <button className="btn" onClick={async () => {
          try {
            const body: any = {
              ...payrails,
              api_key: apiKey || null,
              result_selectors: JSON.parse(resultMapText || "{}"),
              threeds_selectors: JSON.parse(threedsText || "[]"),
              sandbox_cards: JSON.parse(cardsText || "{}"),
            };
            delete body.has_api_key; delete body.id;
            const saved = await api("/payrails-config", { method: "PUT", body: JSON.stringify(body) });
            setPayrails(saved);
            setApiKey("");
            setMsg("Payrails 已保存（无明文 api_key 回传）");
          } catch (e: any) {
            setMsg(e.message || String(e));
          }
        }}>保存 Payrails</button>
      </div>
      {msg && <p className="text-sm text-accent-good">{msg}</p>}
    </div>
  );
}
