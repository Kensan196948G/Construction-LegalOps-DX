"use client";
import { useState } from "react";

const SETTINGS = [
  { id: "n1", label: "ワークフロー承認依頼", desc: "自分が担当ステップに到達したときに通知", defaultOn: true },
  { id: "n2", label: "ワークフロー差戻し", desc: "申請が差戻しになったときに通知", defaultOn: true },
  { id: "n3", label: "AI レビュー完了", desc: "AI レビューが完了したときに通知", defaultOn: true },
  { id: "n4", label: "高リスク検出", desc: "critical または high リスクが検出されたときに通知", defaultOn: true },
  { id: "n5", label: "契約期限アラート", desc: "契約終了日 30 日前・14 日前・7 日前に通知", defaultOn: true },
  { id: "n6", label: "コンプライアンス違反検出", desc: "不適合項目が検出されたときに通知", defaultOn: true },
  { id: "n7", label: "週次サマリーレポート", desc: "毎週月曜に週間レポートをメール送信", defaultOn: false },
  { id: "n8", label: "監査ログ出力完了", desc: "月次監査ログの生成完了時に通知", defaultOn: false },
];

export function NotificationSettingsPanel() {
  const [states, setStates] = useState<Record<string, boolean>>(
    Object.fromEntries(SETTINGS.map(s => [s.id, s.defaultOn]))
  );

  const toggle = (id: string) => setStates(prev => ({ ...prev, [id]: !prev[id] }));

  return (
    <div className="space-y-2">
      {SETTINGS.map(s => (
        <div key={s.id} className="flex items-center justify-between rounded-md border p-3">
          <div>
            <p className="text-sm font-medium">{s.label}</p>
            <p className="text-xs text-muted-foreground">{s.desc}</p>
          </div>
          <button
            role="switch"
            aria-checked={states[s.id]}
            onClick={() => toggle(s.id)}
            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
              states[s.id] ? "bg-primary" : "bg-muted"
            }`}
          >
            <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
              states[s.id] ? "translate-x-6" : "translate-x-1"
            }`} />
          </button>
        </div>
      ))}
    </div>
  );
}
export default NotificationSettingsPanel;
