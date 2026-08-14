// Mock data matching the design prototype — replace with API calls when endpoints are ready.

export const CONTRACT_TYPES = [
  "工事請負契約", "業務委託契約", "資材購入契約", "下請契約",
  "設計監理契約", "賃貸借契約", "秘密保持契約", "売買契約", "覚書", "JV", "その他",
];

export const COMPANIES = [
  "みらい建設工業(株)", "さくら土木(株)", "(株)やまびこ設計事務所", "ひかり資材(株)",
  "(株)つばさ組", "あおぞらコンサルタント(株)", "北信電設(株)", "(株)はるか建材",
  "西陵工業(株)", "(株)きさらぎ設備", "みらいセメント商事(株)", "(株)ほしぞら工務店",
];

export const DEPARTMENTS = ["法務部", "工事部", "管理部", "営業部", "設計部", "総務部"];

export type RiskLevel = "low" | "medium" | "high" | "critical";
export type AppStatus = "draft" | "submitted" | "under_review" | "approved" | "rejected" | "withdrawn";

export const APP_STATUS_LABELS: Record<AppStatus, string> = {
  draft: "下書き",
  submitted: "申請中",
  under_review: "審査中",
  approved: "承認済み",
  rejected: "差戻し",
  withdrawn: "取下げ",
};

export const APP_TYPES = ["新規契約", "変更契約", "契約更新", "契約解除", "緊急レビュー", "顧問弁護士確認"];

export interface ContractApplication {
  id: string;
  type: string;
  title: string;
  applicant: string;
  dept: string;
  amount: number;
  urgency: "緊急" | "通常" | "低";
  status: AppStatus;
  submittedAt: string;
  projectName: string;
}

export const CONTRACT_APPLICATIONS: ContractApplication[] = [
  { id: "APP-2026-0001", type: "新規契約", title: "工事請負契約（みらい建設工業(株)）", applicant: "田中 太郎", dept: "法務部", amount: 120000000, urgency: "緊急", status: "submitted", submittedAt: "2026/05/10", projectName: "みらい北幹線道路補修工事" },
  { id: "APP-2026-0002", type: "変更契約", title: "業務委託契約（さくら土木(株)）", applicant: "鈴木 花子", dept: "法務部", amount: 35000000, urgency: "緊急", status: "under_review", submittedAt: "2026/05/08", projectName: "ひかり町駅前再開発" },
  { id: "APP-2026-0003", type: "契約更新", title: "資材購入契約（ひかり資材(株)）", applicant: "佐藤 一郎", dept: "工事部", amount: 8900000, urgency: "通常", status: "approved", submittedAt: "2026/05/05", projectName: "あおば港防波堤改修" },
  { id: "APP-2026-0004", type: "契約解除", title: "下請契約（(株)つばさ組）", applicant: "山田 美咲", dept: "工事部", amount: 25000000, urgency: "通常", status: "draft", submittedAt: "2026/05/03", projectName: "こまくさ川橋梁架替" },
  { id: "APP-2026-0005", type: "緊急レビュー", title: "設計監理契約（(株)やまびこ設計事務所）", applicant: "高橋 健二", dept: "管理部", amount: 15000000, urgency: "通常", status: "submitted", submittedAt: "2026/05/01", projectName: "みらい都市トンネル補強" },
  { id: "APP-2026-0006", type: "顧問弁護士確認", title: "賃貸借契約（みらいリース(株)）", applicant: "伊藤 直美", dept: "総務部", amount: 3500000, urgency: "低", status: "rejected", submittedAt: "2026/04/28", projectName: "みらい北幹線道路補修工事" },
  { id: "APP-2026-0007", type: "新規契約", title: "秘密保持契約（みらい中央法律事務所）", applicant: "渡辺 誠", dept: "法務部", amount: 1200000, urgency: "低", status: "approved", submittedAt: "2026/04/25", projectName: "ひかり町駅前再開発" },
  { id: "APP-2026-0008", type: "変更契約", title: "工事請負契約（みなと建設(株)）", applicant: "中村 裕子", dept: "営業部", amount: 48000000, urgency: "低", status: "under_review", submittedAt: "2026/04/22", projectName: "あおば港防波堤改修" },
];

export type ConstructionLegalStatus = "ok" | "warning" | "ng";
export const CL_STATUS_LABELS: Record<ConstructionLegalStatus, string> = {
  ok: "適合",
  warning: "要確認",
  ng: "不適合",
};

export interface ConstructionCheck {
  id: string;
  law: string;
  item: string;
  target: string;
  status: ConstructionLegalStatus;
  detail: string;
  checkedAt: string;
  checker: string;
}

export const CONSTRUCTION_CHECKS: ConstructionCheck[] = [
  { id: "cl1", law: "建設業法", item: "第22条 — 一括下請負の禁止", target: "下請契約書（さくら土木）", status: "ok", detail: "一括下請負に該当しないことを確認", checkedAt: "2026/05/14", checker: "田中 太郎" },
  { id: "cl2", law: "建設業法", item: "第19条 — 契約書面の交付義務", target: "工事請負契約（みらい建設工業）", status: "ok", detail: "書面交付済み、要件充足を確認", checkedAt: "2026/05/13", checker: "鈴木 花子" },
  { id: "cl3", law: "下請法", item: "第2条の4 — 支払期日（60日ルール）", target: "下請契約書（つばさ組）", status: "warning", detail: "支払期日が納品後75日に設定。60日ルール抵触の可能性", checkedAt: "2026/05/12", checker: "田中 太郎" },
  { id: "cl4", law: "建設業法", item: "第26条 — 主任技術者の配置", target: "みらい北幹線道路補修工事", status: "ng", detail: "主任技術者の配置届が未提出", checkedAt: "2026/05/12", checker: "佐藤 一郎" },
  { id: "cl5", law: "労働安全衛生法", item: "第30条 — 特定元方事業者の義務", target: "ひかり町駅前再開発工事", status: "ok", detail: "統括安全衛生責任者を選任済み", checkedAt: "2026/05/11", checker: "佐藤 一郎" },
  { id: "cl6", law: "建設業法", item: "第19条の3 — 不当な使用資材等の購入強制の禁止", target: "資材購入契約（ひかり資材）", status: "warning", detail: "特定メーカー指定条項あり、該当性を要確認", checkedAt: "2026/05/10", checker: "田中 太郎" },
  { id: "cl7", law: "下請法", item: "第4条 — 書面の交付義務", target: "下請契約書（こまくさ組）", status: "ok", detail: "3条書面の交付済みを確認", checkedAt: "2026/05/09", checker: "鈴木 花子" },
  { id: "cl8", law: "建設業法", item: "第24条の5 — 特定建設業者の下請代金の支払", target: "あおば港防波堤改修工事", status: "ok", detail: "引渡し後50日以内の支払を確認", checkedAt: "2026/05/08", checker: "田中 太郎" },
  { id: "cl9", law: "公共工事入札契約適正化法", item: "第15条 — 施工体制台帳の提出", target: "こまくさ川橋梁架替工事", status: "warning", detail: "二次下請の記載が不完全、要修正", checkedAt: "2026/05/07", checker: "佐藤 一郎" },
];

export interface ContractDeadline {
  id: string;
  title: string;
  type: string;
  counterparty: string;
  expiresAt: string;
  daysLeft: number;
  autoRenew: boolean;
  guaranteePeriod: string;
  owner: string;
  riskLevel: RiskLevel;
}

export const CONTRACT_DEADLINES: ContractDeadline[] = [
  { id: "CTR-2026-0001", title: "工事請負契約（みらい建設工業(株)）", type: "工事請負契約", counterparty: "みらい建設工業(株)", expiresAt: "2026/05/20", daysLeft: 4, autoRenew: false, guaranteePeriod: "2年", owner: "田中 太郎", riskLevel: "high" },
  { id: "CTR-2026-0002", title: "業務委託契約（さくら土木(株)）", type: "業務委託契約", counterparty: "さくら土木(株)", expiresAt: "2026/06/01", daysLeft: 16, autoRenew: true, guaranteePeriod: "—", owner: "鈴木 花子", riskLevel: "medium" },
  { id: "CTR-2026-0003", title: "資材購入契約（ひかり資材(株)）", type: "資材購入契約", counterparty: "ひかり資材(株)", expiresAt: "2026/06/15", daysLeft: 30, autoRenew: false, guaranteePeriod: "—", owner: "佐藤 一郎", riskLevel: "low" },
  { id: "CTR-2026-0004", title: "下請契約（(株)つばさ組）", type: "下請契約", counterparty: "(株)つばさ組", expiresAt: "2026/07/01", daysLeft: 46, autoRenew: true, guaranteePeriod: "2年", owner: "山田 美咲", riskLevel: "medium" },
  { id: "CTR-2026-0005", title: "設計監理契約（(株)やまびこ設計事務所）", type: "設計監理契約", counterparty: "(株)やまびこ設計事務所", expiresAt: "2026/08/01", daysLeft: 77, autoRenew: false, guaranteePeriod: "—", owner: "高橋 健二", riskLevel: "low" },
  { id: "CTR-2026-0006", title: "賃貸借契約（みらいリース(株)）", type: "賃貸借契約", counterparty: "みらいリース(株)", expiresAt: "2026/09/01", daysLeft: 108, autoRenew: true, guaranteePeriod: "—", owner: "伊藤 直美", riskLevel: "low" },
  { id: "CTR-2026-0007", title: "秘密保持契約（みらい中央法律事務所）", type: "秘密保持契約", counterparty: "みらい中央法律事務所", expiresAt: "2026/11/01", daysLeft: 169, autoRenew: false, guaranteePeriod: "—", owner: "渡辺 誠", riskLevel: "low" },
  { id: "CTR-2026-0008", title: "工事請負契約（みなと建設(株)）", type: "工事請負契約", counterparty: "みなと建設(株)", expiresAt: "2026/12/31", daysLeft: 229, autoRenew: true, guaranteePeriod: "2年", owner: "中村 裕子", riskLevel: "medium" },
];

export interface Partner {
  id: string;
  name: string;
  type: string;
  permitNumber: string;
  permitExpiry: string;
  antiSocialCheck: string;
  antiSocialDate: string | null;
  insurance: string;
  contractCount: number;
  riskLevel: RiskLevel;
  lastTransaction: string;
}

export const PARTNERS: Partner[] = [
  { id: "PTR-0001", name: "みらい建設工業(株)", type: "元請", permitNumber: "国土交通大臣許可（般-2024）第010000号", permitExpiry: "2026/09/15", antiSocialCheck: "確認済", antiSocialDate: "2026/01/10", insurance: "加入済", contractCount: 8, riskLevel: "low", lastTransaction: "2026/05/10" },
  { id: "PTR-0002", name: "さくら土木(株)", type: "元請", permitNumber: "国土交通大臣許可（般-2025）第010137号", permitExpiry: "2026/11/20", antiSocialCheck: "確認済", antiSocialDate: "2026/02/05", insurance: "加入済", contractCount: 5, riskLevel: "low", lastTransaction: "2026/05/08" },
  { id: "PTR-0003", name: "(株)やまびこ設計事務所", type: "元請", permitNumber: "国土交通大臣許可（般-2024）第010274号", permitExpiry: "2027/03/10", antiSocialCheck: "確認済", antiSocialDate: "2026/03/15", insurance: "加入済", contractCount: 3, riskLevel: "low", lastTransaction: "2026/04/20" },
  { id: "PTR-0004", name: "ひかり資材(株)", type: "元請", permitNumber: "国土交通大臣許可（般-2025）第010411号", permitExpiry: "2026/07/01", antiSocialCheck: "確認済", antiSocialDate: "2026/01/20", insurance: "加入済", contractCount: 7, riskLevel: "medium", lastTransaction: "2026/05/12" },
  { id: "PTR-0005", name: "(株)つばさ組", type: "下請（一次）", permitNumber: "東京都知事許可（般-2024）第010548号", permitExpiry: "2026/10/05", antiSocialCheck: "確認済", antiSocialDate: "2025/12/01", insurance: "加入済", contractCount: 4, riskLevel: "low", lastTransaction: "2026/04/15" },
  { id: "PTR-0006", name: "あおぞらコンサルタント(株)", type: "下請（一次）", permitNumber: "東京都知事許可（般-2025）第010685号", permitExpiry: "2027/01/15", antiSocialCheck: "確認済", antiSocialDate: "2026/02/28", insurance: "加入済", contractCount: 2, riskLevel: "low", lastTransaction: "2026/03/20" },
  { id: "PTR-0007", name: "北信電設(株)", type: "下請（一次）", permitNumber: "埼玉県知事許可（般-2024）第010822号", permitExpiry: "2026/08/20", antiSocialCheck: "確認済", antiSocialDate: "2026/01/05", insurance: "加入済", contractCount: 6, riskLevel: "medium", lastTransaction: "2026/05/01" },
  { id: "PTR-0008", name: "(株)はるか建材", type: "下請（一次）", permitNumber: "神奈川県知事許可（般-2025）第010959号", permitExpiry: "2027/02/28", antiSocialCheck: "確認済", antiSocialDate: "2026/03/01", insurance: "加入済", contractCount: 3, riskLevel: "low", lastTransaction: "2026/04/08" },
  { id: "PTR-0009", name: "西陵工業(株)", type: "下請（二次）", permitNumber: "千葉県知事許可（般-2023）第011096号", permitExpiry: "2026/06/10", antiSocialCheck: "確認済", antiSocialDate: "2025/11/15", insurance: "加入済", contractCount: 1, riskLevel: "low", lastTransaction: "2026/03/15" },
  { id: "PTR-0010", name: "(株)きさらぎ設備", type: "下請（二次）", permitNumber: "群馬県知事許可（般-2024）第011233号", permitExpiry: "2026/05/30", antiSocialCheck: "未確認", antiSocialDate: null, insurance: "未確認", contractCount: 2, riskLevel: "high", lastTransaction: "2026/04/30" },
  { id: "PTR-0011", name: "みらいセメント商事(株)", type: "下請（二次）", permitNumber: "国土交通大臣許可（般-2025）第011370号", permitExpiry: "2027/04/15", antiSocialCheck: "確認済", antiSocialDate: "2026/04/01", insurance: "加入済", contractCount: 1, riskLevel: "low", lastTransaction: "2026/02/10" },
  { id: "PTR-0012", name: "(株)ほしぞら工務店", type: "下請（二次）", permitNumber: "東京都知事許可（般-2024）第011507号", permitExpiry: "2026/09/30", antiSocialCheck: "確認済", antiSocialDate: "2026/03/20", insurance: "加入済", contractCount: 1, riskLevel: "low", lastTransaction: "2026/01/25" },
];

export const DISPUTE_TYPES = ["工期遅延", "追加工事費用", "品質不良", "近隣クレーム", "下請トラブル", "未払い・支払遅延"];

export type DisputeStatus = "open" | "investigating" | "resolved" | "escalated";
export const DISPUTE_STATUS_LABELS: Record<DisputeStatus, string> = {
  open: "対応中",
  investigating: "調査中",
  resolved: "解決済み",
  escalated: "エスカレーション",
};

export interface Dispute {
  id: string;
  type: string;
  title: string;
  counterparty: string;
  status: DisputeStatus;
  amount: number | null;
  registeredAt: string;
  assignee: string;
  priority: "高" | "中" | "低";
  description: string;
}

export const DISPUTES: Dispute[] = [
  { id: "DSP-2026-0001", type: "工期遅延", title: "工期延長に伴う追加費用 — みらい北幹線補修", counterparty: "みらい建設工業(株)", status: "open", amount: 15000000, registeredAt: "2026/04/01", assignee: "田中 太郎", priority: "高", description: "工期延長に伴う追加費用の請求。発注者との費用分担について協議中。" },
  { id: "DSP-2026-0002", type: "追加工事費用", title: "施工品質に関する是正要求 — ひかり町駅前再開発", counterparty: "さくら土木(株)", status: "escalated", amount: 8000000, registeredAt: "2026/04/10", assignee: "鈴木 花子", priority: "高", description: "施工品質に関する是正要求。顧問弁護士と対応方針を協議。" },
  { id: "DSP-2026-0003", type: "品質不良", title: "近隣住民からの騒音苦情 — 横浜港防波堤", counterparty: "(株)やまびこ設計事務所", status: "investigating", amount: 2500000, registeredAt: "2026/04/20", assignee: "佐藤 一郎", priority: "中", description: "近隣住民からの騒音苦情。防音対策の実施と補償交渉を並行して進める。" },
  { id: "DSP-2026-0004", type: "近隣クレーム", title: "下請代金の支払条件 — 多摩川橋梁", counterparty: "ひかり資材(株)", status: "open", amount: null, registeredAt: "2026/04/25", assignee: "田中 太郎", priority: "中", description: "下請代金の支払条件に関する協議。60日ルール遵守を確認中。" },
  { id: "DSP-2026-0005", type: "下請トラブル", title: "追加工事費用負担 — 首都圏トンネル", counterparty: "(株)つばさ組", status: "resolved", amount: 5000000, registeredAt: "2026/03/15", assignee: "鈴木 花子", priority: "中", description: "追加工事の費用負担に関する紛争。2026/05/10に和解合意。" },
  { id: "DSP-2026-0006", type: "未払い・支払遅延", title: "工事遅延による損害賠償 — はるか町再開発", counterparty: "あおぞらコンサルタント(株)", status: "investigating", amount: null, registeredAt: "2026/03/01", assignee: "佐藤 一郎", priority: "低", description: "工事遅延による損害賠償請求。過失割合を調査中。" },
  { id: "DSP-2026-0007", type: "工期遅延", title: "品質検査不合格による手戻り — つばさ市地下道", counterparty: "北信電設(株)", status: "resolved", amount: 1200000, registeredAt: "2026/02/20", assignee: "渡辺 誠", priority: "低", description: "品質検査不合格による手戻り費用の分担について解決済み。" },
  { id: "DSP-2026-0008", type: "未払い・支払遅延", title: "支払遅延に対する督促 — みらいビル", counterparty: "(株)はるか建材", status: "open", amount: 3500000, registeredAt: "2026/04/30", assignee: "田中 太郎", priority: "低", description: "支払遅延に対する督促。支払計画書の提出を依頼中。" },
];

// ============================================================
// Server Page Mock Data — contracts / reviews / workflows / risks / knowledge / templates / audit
// ============================================================

export type ContractStatus = "draft" | "in_review" | "approved" | "pending_approval" | "expired" | "archived";
export const CONTRACT_STATUS_LABELS: Record<ContractStatus, string> = {
  draft: "下書き", in_review: "レビュー中", approved: "承認済み",
  pending_approval: "承認待ち", expired: "期限切れ", archived: "アーカイブ",
};

export interface MockContract {
  id: string; title: string; counterparty: string; contractType: string;
  amount: number | null; status: ContractStatus; riskLevel: RiskLevel; updatedAt: string;
}

export const MOCK_CONTRACTS: MockContract[] = [
  { id: "CTR-2026-0001", title: "工事請負契約（みらい建設工業(株)）", counterparty: "みらい建設工業(株)", contractType: "工事請負契約", amount: 120000000, status: "approved", riskLevel: "high", updatedAt: "2026/05/14" },
  { id: "CTR-2026-0002", title: "業務委託契約（さくら土木(株)）", counterparty: "さくら土木(株)", contractType: "業務委託契約", amount: 35000000, status: "in_review", riskLevel: "medium", updatedAt: "2026/05/13" },
  { id: "CTR-2026-0003", title: "資材購入契約（ひかり資材(株)）", counterparty: "ひかり資材(株)", contractType: "資材購入契約", amount: 8900000, status: "pending_approval", riskLevel: "low", updatedAt: "2026/05/12" },
  { id: "CTR-2026-0004", title: "下請契約（(株)つばさ組）", counterparty: "(株)つばさ組", contractType: "下請契約", amount: 25000000, status: "in_review", riskLevel: "critical", updatedAt: "2026/05/11" },
  { id: "CTR-2026-0005", title: "設計監理契約（(株)やまびこ設計事務所）", counterparty: "(株)やまびこ設計事務所", contractType: "設計監理契約", amount: 15000000, status: "approved", riskLevel: "low", updatedAt: "2026/05/10" },
  { id: "CTR-2026-0006", title: "賃貸借契約（みらいリース(株)）", counterparty: "みらいリース(株)", contractType: "賃貸借契約", amount: 3500000, status: "draft", riskLevel: "low", updatedAt: "2026/05/09" },
  { id: "CTR-2026-0007", title: "秘密保持契約（みらい中央法律事務所）", counterparty: "みらい中央法律事務所", contractType: "秘密保持契約", amount: 1200000, status: "approved", riskLevel: "low", updatedAt: "2026/05/08" },
  { id: "CTR-2026-0008", title: "工事請負契約（みなと建設(株)）", counterparty: "みなと建設(株)", contractType: "工事請負契約", amount: 48000000, status: "in_review", riskLevel: "medium", updatedAt: "2026/05/07" },
  { id: "CTR-2026-0009", title: "業務委託契約（あおぞらコンサルタント(株)）", counterparty: "あおぞらコンサルタント(株)", contractType: "業務委託契約", amount: 12000000, status: "pending_approval", riskLevel: "medium", updatedAt: "2026/05/06" },
  { id: "CTR-2026-0010", title: "資材購入契約（みらいセメント商事(株)）", counterparty: "みらいセメント商事(株)", contractType: "資材購入契約", amount: 7500000, status: "approved", riskLevel: "low", updatedAt: "2026/05/05" },
  { id: "CTR-2026-0011", title: "下請契約（(株)こまくさ組）", counterparty: "(株)こまくさ組", contractType: "下請契約", amount: 18000000, status: "expired", riskLevel: "high", updatedAt: "2026/04/30" },
  { id: "CTR-2026-0012", title: "工事請負契約（(株)ほしぞら工務店）", counterparty: "(株)ほしぞら工務店", contractType: "工事請負契約", amount: 250000000, status: "approved", riskLevel: "medium", updatedAt: "2026/04/28" },
  { id: "CTR-2026-0013", title: "設計監理契約（(株)みさき測量）", counterparty: "(株)みさき測量", contractType: "設計監理契約", amount: 9800000, status: "archived", riskLevel: "low", updatedAt: "2026/04/20" },
  { id: "CTR-2026-0014", title: "業務委託契約（北信電設(株)）", counterparty: "北信電設(株)", contractType: "業務委託契約", amount: 22000000, status: "in_review", riskLevel: "high", updatedAt: "2026/05/15" },
  { id: "CTR-2026-0015", title: "資材購入契約（(株)はるか建材）", counterparty: "(株)はるか建材", contractType: "資材購入契約", amount: 5500000, status: "draft", riskLevel: "low", updatedAt: "2026/05/16" },
];

export type ReviewStatus = "completed" | "in_progress" | "pending_confirmation";
export const REVIEW_STATUS_LABELS: Record<ReviewStatus, string> = {
  completed: "完了", in_progress: "レビュー中", pending_confirmation: "確認待ち",
};

export interface MockReview {
  id: string; contractId: string; contractTitle: string; aiModel: string;
  riskLevel: RiskLevel; issuesCount: number; status: ReviewStatus;
  reviewerConfirmed: boolean; completedAt: string | null;
}

export const MOCK_REVIEWS: MockReview[] = [
  { id: "REV-0001", contractId: "CTR-2026-0001", contractTitle: "工事請負契約（みらい建設工業(株)）", aiModel: "claude-opus-4-7", riskLevel: "high", issuesCount: 4, status: "completed", reviewerConfirmed: true, completedAt: "2026/05/14" },
  { id: "REV-0002", contractId: "CTR-2026-0002", contractTitle: "業務委託契約（さくら土木(株)）", aiModel: "claude-opus-4-7", riskLevel: "medium", issuesCount: 2, status: "in_progress", reviewerConfirmed: false, completedAt: null },
  { id: "REV-0003", contractId: "CTR-2026-0004", contractTitle: "下請契約（(株)つばさ組）", aiModel: "claude-opus-4-7", riskLevel: "critical", issuesCount: 6, status: "completed", reviewerConfirmed: false, completedAt: "2026/05/11" },
  { id: "REV-0004", contractId: "CTR-2026-0008", contractTitle: "工事請負契約（みなと建設(株)）", aiModel: "claude-opus-4-7", riskLevel: "medium", issuesCount: 3, status: "pending_confirmation", reviewerConfirmed: false, completedAt: "2026/05/07" },
  { id: "REV-0005", contractId: "CTR-2026-0009", contractTitle: "業務委託契約（あおぞらコンサルタント(株)）", aiModel: "claude-opus-4-7", riskLevel: "medium", issuesCount: 2, status: "completed", reviewerConfirmed: true, completedAt: "2026/05/06" },
  { id: "REV-0006", contractId: "CTR-2026-0011", contractTitle: "下請契約（(株)こまくさ組）", aiModel: "claude-opus-4-7", riskLevel: "high", issuesCount: 5, status: "completed", reviewerConfirmed: true, completedAt: "2026/04/29" },
  { id: "REV-0007", contractId: "CTR-2026-0012", contractTitle: "工事請負契約（(株)ほしぞら工務店）", aiModel: "claude-opus-4-7", riskLevel: "medium", issuesCount: 1, status: "completed", reviewerConfirmed: true, completedAt: "2026/04/27" },
  { id: "REV-0008", contractId: "CTR-2026-0014", contractTitle: "業務委託契約（北信電設(株)）", aiModel: "claude-opus-4-7", riskLevel: "high", issuesCount: 4, status: "in_progress", reviewerConfirmed: false, completedAt: null },
];

export type WorkflowStatus = "in_progress" | "approved" | "rejected" | "returned" | "withdrawn";
export type WorkflowRoute = "A1" | "A2" | "B1" | "B2" | "C1" | "C2" | "D1";
export const WORKFLOW_STATUS_LABELS: Record<WorkflowStatus, string> = {
  in_progress: "審査中", approved: "承認済み", rejected: "否決", returned: "差戻し", withdrawn: "取下げ",
};

export interface MockWorkflow {
  id: string; contractId: string; contractTitle: string; route: WorkflowRoute;
  currentStep: string; waitingFor: string; status: WorkflowStatus;
  requiresOutsideCounsel: boolean; dueDate: string | null; updatedAt: string;
}

export const MOCK_WORKFLOWS: MockWorkflow[] = [
  { id: "WF-0001", contractId: "CTR-2026-0001", contractTitle: "工事請負契約（みらい建設工業(株)）", route: "A2", currentStep: "部門長承認", waitingFor: "佐藤 一郎", status: "in_progress", requiresOutsideCounsel: true, dueDate: "2026/05/20", updatedAt: "2026/05/14" },
  { id: "WF-0002", contractId: "CTR-2026-0003", contractTitle: "資材購入契約（ひかり資材(株)）", route: "B1", currentStep: "法務リード承認", waitingFor: "田中 太郎", status: "in_progress", requiresOutsideCounsel: false, dueDate: "2026/05/18", updatedAt: "2026/05/12" },
  { id: "WF-0003", contractId: "CTR-2026-0005", contractTitle: "設計監理契約（(株)やまびこ設計事務所）", route: "B2", currentStep: "完了", waitingFor: "—", status: "approved", requiresOutsideCounsel: false, dueDate: null, updatedAt: "2026/05/10" },
  { id: "WF-0004", contractId: "CTR-2026-0009", contractTitle: "業務委託契約（あおぞらコンサルタント(株)）", route: "C1", currentStep: "法務担当レビュー", waitingFor: "鈴木 花子", status: "in_progress", requiresOutsideCounsel: false, dueDate: "2026/05/22", updatedAt: "2026/05/06" },
  { id: "WF-0005", contractId: "CTR-2026-0012", contractTitle: "工事請負契約（(株)ほしぞら工務店）", route: "A1", currentStep: "完了", waitingFor: "—", status: "approved", requiresOutsideCounsel: true, dueDate: null, updatedAt: "2026/04/28" },
  { id: "WF-0006", contractId: "CTR-2026-0004", contractTitle: "下請契約（(株)つばさ組）", route: "D1", currentStep: "弁護士確認", waitingFor: "外部弁護士", status: "in_progress", requiresOutsideCounsel: true, dueDate: "2026/05/25", updatedAt: "2026/05/11" },
  { id: "WF-0007", contractId: "CTR-2026-0007", contractTitle: "秘密保持契約（みらい中央法律事務所）", route: "C2", currentStep: "完了", waitingFor: "—", status: "approved", requiresOutsideCounsel: false, dueDate: null, updatedAt: "2026/05/08" },
  { id: "WF-0008", contractId: "CTR-2026-0014", contractTitle: "業務委託契約（北信電設(株)）", route: "B1", currentStep: "法務リード承認", waitingFor: "田中 太郎", status: "returned", requiresOutsideCounsel: false, dueDate: "2026/05/19", updatedAt: "2026/05/15" },
];

export type RiskItemStatus = "open" | "mitigated" | "accepted" | "closed";
export const RISK_ITEM_STATUS_LABELS: Record<RiskItemStatus, string> = {
  open: "未対応", mitigated: "軽減済み", accepted: "受容", closed: "解消",
};

export interface MockRisk {
  id: string; contractId: string; contractTitle: string; category: string;
  level: RiskLevel; score: number; description: string;
  status: RiskItemStatus; owner: string | null; detectedAt: string;
  probability: 1 | 2 | 3 | 4; impact: 1 | 2 | 3 | 4;
}

export const MOCK_RISKS: MockRisk[] = [
  { id: "RSK-0001", contractId: "CTR-2026-0004", contractTitle: "下請契約（(株)つばさ組）", category: "下請法", level: "critical", score: 88, description: "支払期日が納品後75日に設定されており、下請法第2条の4（60日ルール）に抵触する可能性があります。", status: "open", owner: "田中 太郎", detectedAt: "2026/05/11", probability: 4, impact: 4 },
  { id: "RSK-0002", contractId: "CTR-2026-0001", contractTitle: "工事請負契約（みらい建設工業(株)）", category: "建設業法", level: "high", score: 72, description: "第7条の解除条項が発注者に一方的に有利であり、建設業法第19条の3に抵触する恐れがあります。", status: "open", owner: "鈴木 花子", detectedAt: "2026/05/14", probability: 3, impact: 4 },
  { id: "RSK-0003", contractId: "CTR-2026-0001", contractTitle: "工事請負契約（みらい建設工業(株)）", category: "損害賠償", level: "high", score: 65, description: "損害賠償の上限条項が設定されておらず、過大なリスク負担となる可能性があります。", status: "open", owner: "田中 太郎", detectedAt: "2026/05/14", probability: 3, impact: 3 },
  { id: "RSK-0004", contractId: "CTR-2026-0002", contractTitle: "業務委託契約（さくら土木(株)）", category: "工期", level: "medium", score: 45, description: "工期延長条件が不明確で、天候不順・不可抗力時の対応が未定義です。", status: "open", owner: "鈴木 花子", detectedAt: "2026/05/13", probability: 3, impact: 2 },
  { id: "RSK-0005", contractId: "CTR-2026-0011", contractTitle: "下請契約（(株)こまくさ組）", category: "建設業法", level: "high", score: 70, description: "主任技術者の配置届が未提出であり、建設業法第26条違反の可能性があります。", status: "open", owner: "佐藤 一郎", detectedAt: "2026/04/30", probability: 4, impact: 3 },
  { id: "RSK-0006", contractId: "CTR-2026-0008", contractTitle: "工事請負契約（みなと建設(株)）", category: "秘密保持", level: "medium", score: 38, description: "秘密情報の定義が過度に広範であり、実務上の適用が困難です。", status: "accepted", owner: "渡辺 誠", detectedAt: "2026/05/07", probability: 2, impact: 2 },
  { id: "RSK-0007", contractId: "CTR-2026-0005", contractTitle: "設計監理契約（(株)やまびこ設計事務所）", category: "検査・引渡し", level: "medium", score: 42, description: "検査期間が7日間と設定されており、工事規模に対して不十分な可能性があります。", status: "mitigated", owner: "田中 太郎", detectedAt: "2026/05/10", probability: 2, impact: 3 },
  { id: "RSK-0008", contractId: "CTR-2026-0012", contractTitle: "工事請負契約（(株)ほしぞら工務店）", category: "下請法", level: "low", score: 22, description: "支払条件の記載が一部不明確ですが、口頭での合意があることを確認しました。", status: "closed", owner: "鈴木 花子", detectedAt: "2026/04/28", probability: 1, impact: 2 },
  { id: "RSK-0009", contractId: "CTR-2026-0014", contractTitle: "業務委託契約（北信電設(株)）", category: "建設業法", level: "high", score: 68, description: "施工体制台帳の二次下請記載が不完全で、公共工事入札適正化法第15条に抵触する可能性があります。", status: "open", owner: "佐藤 一郎", detectedAt: "2026/05/15", probability: 3, impact: 3 },
  { id: "RSK-0010", contractId: "CTR-2026-0003", contractTitle: "資材購入契約（ひかり資材(株)）", category: "独占禁止法", level: "low", score: 18, description: "特定メーカー指定条項の該当性を確認中。現時点では軽微と判断。", status: "accepted", owner: "田中 太郎", detectedAt: "2026/05/12", probability: 1, impact: 1 },
];

export type KnowledgeSource = "internal_doc" | "precedent" | "faq" | "playbook";
export const KNOWLEDGE_SOURCE_LABELS: Record<KnowledgeSource, string> = {
  internal_doc: "社内文書", precedent: "判例", faq: "FAQ", playbook: "プレイブック",
};

export interface MockKnowledgeItem {
  id: string; title: string; excerpt: string; source: KnowledgeSource;
  category: string; tags: string[]; updatedAt: string; score: number;
}

export const MOCK_KNOWLEDGE: MockKnowledgeItem[] = [
  { id: "K-001", title: "建設業法 第19条の解説と実務上の留意点", excerpt: "建設業法第19条は契約書面の交付義務を定めています。工事請負契約の締結に際しては、工事内容・請負代金額・工期等を記載した書面を交付することが義務付けられています。電子書面での交付も認められています。", source: "internal_doc", category: "建設業法", tags: ["建設業法", "契約書", "書面交付"], updatedAt: "2026/05/10", score: 98 },
  { id: "K-002", title: "下請法における支払期日の遵守について（60日ルール）", excerpt: "下請法第2条の4により、下請代金の支払期日は物品等の受領日から60日以内に定めることが義務付けられています。違反した場合は公正取引委員会による勧告・措置命令の対象となります。", source: "internal_doc", category: "下請法", tags: ["下請法", "支払期日", "60日ルール"], updatedAt: "2026/04/22", score: 95 },
  { id: "K-003", title: "電子帳簿保存法 — 契約書の電子保存要件（2024年改正対応）", excerpt: "電子取引における電子データの保存義務が強化されました。検索要件（取引年月日・取引金額・取引先での検索）を満たすシステムによる保存が必要です。", source: "internal_doc", category: "電子帳簿保存法", tags: ["電子帳簿保存法", "電子保存", "検索要件"], updatedAt: "2026/05/05", score: 92 },
  { id: "K-004", title: "工事請負契約のリスクチェックリスト（社内標準版）", excerpt: "工事請負契約締結前に確認すべき重要事項を整理したチェックリストです。建設業法・下請法・労働安全衛生法の各要件、保険、担保等を網羅しています。", source: "playbook", category: "社内規程", tags: ["チェックリスト", "工事請負", "リスク管理"], updatedAt: "2026/03/15", score: 90 },
  { id: "K-005", title: "反社会的勢力排除条項の標準文言と運用指針", excerpt: "契約書への反社排除条項の挿入は、コンプライアンス上必須です。本文書では標準文言、取引先確認手続き、発見時の対応フローを解説します。", source: "playbook", category: "コンプライアンス", tags: ["反社排除", "コンプライアンス", "標準条項"], updatedAt: "2026/04/01", score: 88 },
  { id: "K-006", title: "【判例】一括下請負の禁止と例外 — 最高裁令和3年判決", excerpt: "建設業法第22条の一括下請負禁止規定について、実質的に施工に関与していない場合の判断基準を示した重要判例。下請業者への指示・監督の実態が重要な判断要素とされた。", source: "precedent", category: "建設業法", tags: ["判例", "一括下請負", "建設業法"], updatedAt: "2026/02/10", score: 85 },
  { id: "K-007", title: "FAQ: AI レビュー結果の法的効力と弁護士確認の必要性", excerpt: "Q: AIが「問題なし」と判断した契約書は弁護士確認なしで締結できますか？ A: いいえ。AI一次レビューは参考情報であり、最終的な法的判断は資格を持つ法務担当者・弁護士が行う必要があります。", source: "faq", category: "AI利用指針", tags: ["AI", "免責", "弁護士確認"], updatedAt: "2026/05/01", score: 82 },
  { id: "K-008", title: "主任技術者・監理技術者の配置要件まとめ", excerpt: "建設業法第26条に基づく技術者配置要件を整理。専任が必要な工事の金額要件（4,000万円以上）、資格要件、兼任可否の判断基準を解説します。", source: "internal_doc", category: "建設業法", tags: ["技術者", "主任技術者", "監理技術者"], updatedAt: "2026/03/20", score: 80 },
];

export type TemplateStatus = "draft" | "published" | "archived";
export const TEMPLATE_STATUS_LABELS: Record<TemplateStatus, string> = {
  draft: "下書き", published: "公開中", archived: "アーカイブ",
};

export interface MockTemplate {
  id: string; title: string; contractType: string; version: string;
  status: TemplateStatus; updatedBy: string; updatedAt: string;
}

export const MOCK_TEMPLATES: MockTemplate[] = [
  { id: "TPL-001", title: "工事請負契約書（公共工事用）", contractType: "工事請負契約", version: "v3.2", status: "published", updatedBy: "田中 太郎", updatedAt: "2026/04/15" },
  { id: "TPL-002", title: "下請工事基本契約書（標準版）", contractType: "下請契約", version: "v2.5", status: "published", updatedBy: "鈴木 花子", updatedAt: "2026/04/20" },
  { id: "TPL-003", title: "業務委託契約書（設計・監理業務）", contractType: "業務委託契約", version: "v1.8", status: "published", updatedBy: "渡辺 誠", updatedAt: "2026/03/10" },
  { id: "TPL-004", title: "資材購入基本契約書", contractType: "資材購入契約", version: "v2.0", status: "published", updatedBy: "田中 太郎", updatedAt: "2026/05/01" },
  { id: "TPL-005", title: "秘密保持契約書（NDA）— 相互開示型", contractType: "秘密保持契約", version: "v1.3", status: "published", updatedBy: "鈴木 花子", updatedAt: "2026/04/28" },
  { id: "TPL-006", title: "建設工事保険付保依頼書", contractType: "工事請負契約", version: "v1.1", status: "published", updatedBy: "佐藤 一郎", updatedAt: "2026/02/18" },
  { id: "TPL-007", title: "工事請負契約書（民間工事用・改訂案）", contractType: "工事請負契約", version: "v4.0-draft", status: "draft", updatedBy: "田中 太郎", updatedAt: "2026/05/16" },
  { id: "TPL-008", title: "設計監理契約書（旧版）", contractType: "設計監理契約", version: "v1.0", status: "archived", updatedBy: "渡辺 誠", updatedAt: "2025/12/01" },
];

export interface MockAuditLog {
  id: string; occurredAt: string;
  actor: { id: string; name: string; role: string };
  action: string; resourceType: string; resourceId: string;
  ipAddress: string | null; userAgent: string | null;
  prevHash: string; hash: string; chainValid: boolean;
}

function fakeHash(seed: number): string {
  return Array.from({ length: 64 }, (_, i) => ((seed * 31 + i * 7) % 16).toString(16)).join("");
}

export const MOCK_AUDIT_LOGS: MockAuditLog[] = [
  { id: "AL-10050", occurredAt: "2026-05-16T14:32:01", actor: { id: "u1", name: "田中 太郎", role: "legal_lead" }, action: "contract.create", resourceType: "contract", resourceId: "CTR-2026-0015", ipAddress: "192.168.0.10", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(1), hash: fakeHash(2), chainValid: true },
  { id: "AL-10049", occurredAt: "2026-05-16T13:21:44", actor: { id: "u2", name: "鈴木 花子", role: "legal_member" }, action: "review.complete", resourceType: "review", resourceId: "REV-0002", ipAddress: "192.168.0.11", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(2), hash: fakeHash(3), chainValid: true },
  { id: "AL-10048", occurredAt: "2026-05-16T11:55:12", actor: { id: "u1", name: "田中 太郎", role: "legal_lead" }, action: "workflow.approve", resourceType: "workflow", resourceId: "WF-0003", ipAddress: "192.168.0.10", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(3), hash: fakeHash(4), chainValid: true },
  { id: "AL-10047", occurredAt: "2026-05-15T16:40:33", actor: { id: "u3", name: "佐藤 一郎", role: "manager" }, action: "contract.update", resourceType: "contract", resourceId: "CTR-2026-0008", ipAddress: "192.168.0.20", userAgent: "Mozilla/5.0 Safari/17", prevHash: fakeHash(4), hash: fakeHash(5), chainValid: true },
  { id: "AL-10046", occurredAt: "2026-05-15T14:22:05", actor: { id: "u2", name: "鈴木 花子", role: "legal_member" }, action: "review.start", resourceType: "review", resourceId: "REV-0008", ipAddress: "192.168.0.11", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(5), hash: fakeHash(6), chainValid: true },
  { id: "AL-10045", occurredAt: "2026-05-15T10:05:58", actor: { id: "u5", name: "高橋 健二", role: "admin" }, action: "user.login", resourceType: "user", resourceId: "u5", ipAddress: "192.168.0.30", userAgent: "Mozilla/5.0 Edge/124", prevHash: fakeHash(6), hash: fakeHash(7), chainValid: true },
  { id: "AL-10044", occurredAt: "2026-05-14T17:30:00", actor: { id: "u1", name: "田中 太郎", role: "legal_lead" }, action: "workflow.approve", resourceType: "workflow", resourceId: "WF-0005", ipAddress: "192.168.0.10", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(7), hash: fakeHash(8), chainValid: true },
  { id: "AL-10043", occurredAt: "2026-05-14T15:18:22", actor: { id: "u2", name: "鈴木 花子", role: "legal_member" }, action: "review.complete", resourceType: "review", resourceId: "REV-0001", ipAddress: "192.168.0.11", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(8), hash: fakeHash(9), chainValid: true },
  { id: "AL-10042", occurredAt: "2026-05-14T09:44:17", actor: { id: "u4", name: "山田 美咲", role: "site_member" }, action: "contract.upload", resourceType: "contract", resourceId: "CTR-2026-0001", ipAddress: "192.168.0.21", userAgent: "Mozilla/5.0 Firefox/125", prevHash: fakeHash(9), hash: fakeHash(10), chainValid: true },
  { id: "AL-10041", occurredAt: "2026-05-13T14:01:49", actor: { id: "u6", name: "伊藤 直美", role: "auditor" }, action: "user.login", resourceType: "user", resourceId: "u6", ipAddress: "192.168.0.40", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(10), hash: fakeHash(11), chainValid: true },
  { id: "AL-10040", occurredAt: "2026-05-13T11:30:05", actor: { id: "u3", name: "佐藤 一郎", role: "manager" }, action: "contract.create", resourceType: "contract", resourceId: "CTR-2026-0014", ipAddress: "192.168.0.20", userAgent: "Mozilla/5.0 Safari/17", prevHash: fakeHash(11), hash: fakeHash(12), chainValid: true },
  { id: "AL-10039", occurredAt: "2026-05-12T16:55:33", actor: { id: "u1", name: "田中 太郎", role: "legal_lead" }, action: "settings.update", resourceType: "system", resourceId: "SYS", ipAddress: "192.168.0.10", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(12), hash: fakeHash(13), chainValid: true },
  { id: "AL-10038", occurredAt: "2026-05-12T10:20:44", actor: { id: "u7", name: "渡辺 誠", role: "legal_member" }, action: "workflow.approve", resourceType: "workflow", resourceId: "WF-0007", ipAddress: "192.168.0.12", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(13), hash: fakeHash(14), chainValid: true },
  { id: "AL-10037", occurredAt: "2026-05-11T15:45:00", actor: { id: "u2", name: "鈴木 花子", role: "legal_member" }, action: "review.start", resourceType: "review", resourceId: "REV-0004", ipAddress: "192.168.0.11", userAgent: "Mozilla/5.0 Chrome/124", prevHash: fakeHash(14), hash: fakeHash(15), chainValid: true },
  { id: "AL-10036", occurredAt: "2026-05-10T09:10:12", actor: { id: "u5", name: "高橋 健二", role: "admin" }, action: "user.login", resourceType: "user", resourceId: "u5", ipAddress: "192.168.0.30", userAgent: "Mozilla/5.0 Edge/124", prevHash: fakeHash(15), hash: fakeHash(16), chainValid: true },
];

// Dashboard KPIs derived from mock data
export const MOCK_DASHBOARD_KPIS = {
  total_contracts: MOCK_CONTRACTS.length,
  in_review: MOCK_CONTRACTS.filter(c => c.status === "in_review").length,
  pending_approval: MOCK_CONTRACTS.filter(c => c.status === "pending_approval").length,
  high_risk_open: MOCK_RISKS.filter(r => (r.level === "high" || r.level === "critical") && r.status === "open").length,
  reviews_this_month: MOCK_REVIEWS.filter(r => r.status === "completed").length,
};

export const MOCK_RISK_DISTRIBUTION = [
  { level: "low" as RiskLevel, count: MOCK_RISKS.filter(r => r.level === "low").length },
  { level: "medium" as RiskLevel, count: MOCK_RISKS.filter(r => r.level === "medium").length },
  { level: "high" as RiskLevel, count: MOCK_RISKS.filter(r => r.level === "high").length },
  { level: "critical" as RiskLevel, count: MOCK_RISKS.filter(r => r.level === "critical").length },
];

// ============================================================
// Compliance Mock Data
// ============================================================
export type ComplianceStatus = "compliant" | "warning" | "non_compliant";
export const COMPLIANCE_STATUS_LABELS: Record<ComplianceStatus, string> = {
  compliant: "適合", warning: "要確認", non_compliant: "不適合",
};

export interface ComplianceItem {
  id: string; law: string; item: string;
  status: ComplianceStatus; lastCheck: string; detail: string;
}

export const MOCK_COMPLIANCE_ITEMS: ComplianceItem[] = [
  { id: "cp1", law: "建設業法", item: "第19条 — 契約書面の交付義務", status: "compliant", lastCheck: "2026/05/10", detail: "書面交付済み。全契約で要件充足を確認。" },
  { id: "cp2", law: "建設業法", item: "第24条の3 — 下請代金の支払", status: "compliant", lastCheck: "2026/05/10", detail: "引渡し後50日以内の支払を確認済み。" },
  { id: "cp3", law: "下請法", item: "第2条の4 — 支払期日（60日ルール）", status: "warning", lastCheck: "2026/05/08", detail: "一部契約で支払期日が75日に設定されており要是正。" },
  { id: "cp4", law: "下請法", item: "第4条 — 書面の交付義務", status: "compliant", lastCheck: "2026/05/08", detail: "3条書面の交付を全契約で確認済み。" },
  { id: "cp5", law: "電子帳簿保存法", item: "第7条 — 電子取引データの保存", status: "compliant", lastCheck: "2026/05/01", detail: "電子データの適切な保存を確認。" },
  { id: "cp6", law: "電子帳簿保存法", item: "検索要件の充足", status: "compliant", lastCheck: "2026/05/01", detail: "取引年月日・取引金額・取引先の検索条件を契約台帳と保存証跡で確認済み。月次監査で継続確認。" },
  { id: "cp7", law: "個人情報保護法", item: "第23条 — 第三者提供の制限", status: "compliant", lastCheck: "2026/04/25", detail: "個人情報の第三者提供は適切な同意のもとで実施。" },
  { id: "cp8", law: "建設業法", item: "第26条 — 主任技術者の配置", status: "non_compliant", lastCheck: "2026/05/12", detail: "みらい北幹線補修工事で主任技術者の配置届が未提出。至急対応要。" },
];

export const MOCK_COMPLIANCE_FRAMEWORKS = [
  { id: "construction_business_act", label: "建設業法",
    passed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "建設業法" && c.status === "compliant").length,
    failed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "建設業法" && c.status === "non_compliant").length,
    na: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "建設業法" && c.status === "warning").length },
  { id: "subcontract_act", label: "下請代金支払遅延等防止法",
    passed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "下請法" && c.status === "compliant").length,
    failed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "下請法" && c.status === "non_compliant").length,
    na: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "下請法" && c.status === "warning").length },
  { id: "electronic_books", label: "電子帳簿保存法",
    passed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "電子帳簿保存法" && c.status === "compliant").length,
    failed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "電子帳簿保存法" && c.status === "non_compliant").length,
    na: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "電子帳簿保存法" && c.status === "warning").length },
  { id: "personal_info", label: "個人情報保護法",
    passed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "個人情報保護法" && c.status === "compliant").length,
    failed: MOCK_COMPLIANCE_ITEMS.filter(c => c.law === "個人情報保護法" && c.status === "non_compliant").length,
    na: 0 },
];

// ============================================================
// Review Detail Mock (issues / suggestions)
// ============================================================
export interface ReviewIssue {
  id: string; target: string; summary: string;
  severity: RiskLevel; detail: string;
}
export interface ReviewSuggestion {
  id: string; target: string; summary: string;
  original: string; proposed: string; rationale: string; confidence: number;
}

export const MOCK_REVIEW_ISSUES: ReviewIssue[] = [
  { id: "i1", target: "第3条 契約金額", summary: "支払条件が下請法に抵触する可能性", severity: "high", detail: "支払期日が納品後90日に設定されており、下請法第2条の4（60日ルール）に違反する可能性があります。至急是正が必要です。" },
  { id: "i2", target: "第7条 解除条項", summary: "一方的解除条項に建設業法上のリスク", severity: "critical", detail: "発注者側からの一方的解除が不当に広く認められており、建設業法第19条の3「不当な使用資材等の購入強制の禁止」に抵触する恐れがあります。" },
  { id: "i3", target: "第12条 損害賠償", summary: "賠償上限が設定されていない", severity: "medium", detail: "損害賠償の上限条項がなく、過大なリスク負担となる可能性があります。契約金額を上限とする条項の追加を推奨します。" },
  { id: "i4", target: "第5条 工期", summary: "工期延長条件が不明確", severity: "medium", detail: "天候不順や不可抗力による工期延長の条件が具体的に定められていません。明確な基準の設定を推奨します。" },
  { id: "i5", target: "第15条 秘密保持", summary: "秘密情報の定義が広すぎる", severity: "low", detail: "秘密情報の範囲が「一切の情報」と定義されており、実務上の運用が困難です。具体的な定義を設けることを推奨します。" },
];

export const MOCK_REVIEW_SUGGESTIONS: ReviewSuggestion[] = [
  { id: "s1", target: "第3条 契約金額", summary: "支払期日を60日以内に短縮", original: "支払いは、納品確認後90日以内に行うものとする。", proposed: "支払いは、納品確認後60日以内に行うものとする。なお、下請法の適用がある場合は同法の定めに従う。", rationale: "下請法第2条の4により、下請代金の支払期日は物品等の受領日から60日以内と定められています。", confidence: 92 },
  { id: "s2", target: "第7条 解除条項", summary: "解除事由の限定と催告手続の追加", original: "甲は、いつでも本契約を解除することができる。", proposed: "甲は、乙が本契約に重大な違反をし、書面による催告後30日以内に是正されない場合に限り、本契約を解除することができる。", rationale: "建設業法第19条の3の趣旨に照らし、一方的な解除権は制限すべきです。", confidence: 88 },
  { id: "s3", target: "第12条 損害賠償", summary: "賠償上限条項の追加", original: "（上限条項なし）", proposed: "本契約に基づく損害賠償の総額は、契約金額を上限とする。ただし、故意または重過失による場合はこの限りでない。", rationale: "無制限の賠償責任は過大なリスクとなるため、契約金額を上限とする条項の追加を推奨します。", confidence: 85 },
];

// Workflow steps for mock
export interface MockWorkflowStep {
  id: string; order: number; label: string; assigneeRole: string; assigneeName: string | null;
  status: "pending" | "in_progress" | "approved" | "rejected" | "returned" | "skipped"; decidedAt: string | null;
}

export const MOCK_WORKFLOW_STEPS: Record<string, MockWorkflowStep[]> = {
  "WF-0001": [
    { id: "s1", order: 1, label: "法務担当レビュー", assigneeRole: "法務担当", assigneeName: "鈴木 花子", status: "approved", decidedAt: "2026/05/12" },
    { id: "s2", order: 2, label: "法務リード承認", assigneeRole: "法務リード", assigneeName: "田中 太郎", status: "approved", decidedAt: "2026/05/13" },
    { id: "s3", order: 3, label: "部門長承認", assigneeRole: "部門長", assigneeName: "佐藤 一郎", status: "in_progress", decidedAt: null },
    { id: "s4", order: 4, label: "弁護士確認", assigneeRole: "顧問弁護士", assigneeName: "外部弁護士", status: "pending", decidedAt: null },
  ],
  "WF-0002": [
    { id: "s1", order: 1, label: "法務担当レビュー", assigneeRole: "法務担当", assigneeName: "鈴木 花子", status: "approved", decidedAt: "2026/05/11" },
    { id: "s2", order: 2, label: "法務リード承認", assigneeRole: "法務リード", assigneeName: "田中 太郎", status: "in_progress", decidedAt: null },
  ],
  "WF-0006": [
    { id: "s1", order: 1, label: "法務担当レビュー", assigneeRole: "法務担当", assigneeName: "鈴木 花子", status: "approved", decidedAt: "2026/05/10" },
    { id: "s2", order: 2, label: "法務リード承認", assigneeRole: "法務リード", assigneeName: "田中 太郎", status: "approved", decidedAt: "2026/05/11" },
    { id: "s3", order: 3, label: "弁護士確認", assigneeRole: "顧問弁護士", assigneeName: "外部弁護士", status: "in_progress", decidedAt: null },
  ],
};
