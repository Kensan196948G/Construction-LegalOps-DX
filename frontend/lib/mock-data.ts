// Mock data matching the design prototype — replace with API calls when endpoints are ready.

export const CONTRACT_TYPES = [
  "工事請負契約", "業務委託契約", "資材購入契約", "下請契約",
  "設計監理契約", "賃貸借契約", "秘密保持契約",
];

export const COMPANIES = [
  "大成建設工業(株)", "鈴木土木(株)", "(株)山田設計事務所", "東日本資材(株)",
  "(株)佐藤組", "中央コンサルタント(株)", "北関東電設(株)", "(株)高橋建材",
  "西部工業(株)", "(株)渡辺設備", "太平洋セメント(株)", "(株)田中工務店",
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
  { id: "APP-2026-0001", type: "新規契約", title: "工事請負契約（大成建設工業(株)）", applicant: "田中 太郎", dept: "法務部", amount: 120000000, urgency: "緊急", status: "submitted", submittedAt: "2026/05/10", projectName: "東名高速道路補修工事" },
  { id: "APP-2026-0002", type: "変更契約", title: "業務委託契約（鈴木土木(株)）", applicant: "鈴木 花子", dept: "法務部", amount: 35000000, urgency: "緊急", status: "under_review", submittedAt: "2026/05/08", projectName: "新宿駅再開発" },
  { id: "APP-2026-0003", type: "契約更新", title: "資材購入契約（東日本資材(株)）", applicant: "佐藤 一郎", dept: "工事部", amount: 8900000, urgency: "通常", status: "approved", submittedAt: "2026/05/05", projectName: "横浜港防波堤改修" },
  { id: "APP-2026-0004", type: "契約解除", title: "下請契約（(株)佐藤組）", applicant: "山田 美咲", dept: "工事部", amount: 25000000, urgency: "通常", status: "draft", submittedAt: "2026/05/03", projectName: "多摩川橋梁架替" },
  { id: "APP-2026-0005", type: "緊急レビュー", title: "設計監理契約（(株)山田設計事務所）", applicant: "高橋 健二", dept: "管理部", amount: 15000000, urgency: "通常", status: "submitted", submittedAt: "2026/05/01", projectName: "首都圏トンネル補強" },
  { id: "APP-2026-0006", type: "顧問弁護士確認", title: "賃貸借契約（関東リース(株)）", applicant: "伊藤 直美", dept: "総務部", amount: 3500000, urgency: "低", status: "rejected", submittedAt: "2026/04/28", projectName: "東名高速道路補修工事" },
  { id: "APP-2026-0007", type: "新規契約", title: "秘密保持契約（東京法律事務所）", applicant: "渡辺 誠", dept: "法務部", amount: 1200000, urgency: "低", status: "approved", submittedAt: "2026/04/25", projectName: "新宿駅再開発" },
  { id: "APP-2026-0008", type: "変更契約", title: "工事請負契約（横浜建設(株)）", applicant: "中村 裕子", dept: "営業部", amount: 48000000, urgency: "低", status: "under_review", submittedAt: "2026/04/22", projectName: "横浜港防波堤改修" },
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
  { id: "cl1", law: "建設業法", item: "第22条 — 一括下請負の禁止", target: "下請契約書（鈴木土木）", status: "ok", detail: "一括下請負に該当しないことを確認", checkedAt: "2026/05/14", checker: "田中 太郎" },
  { id: "cl2", law: "建設業法", item: "第19条 — 契約書面の交付義務", target: "工事請負契約（大成建設工業）", status: "ok", detail: "書面交付済み、要件充足を確認", checkedAt: "2026/05/13", checker: "鈴木 花子" },
  { id: "cl3", law: "下請法", item: "第2条の4 — 支払期日（60日ルール）", target: "下請契約書（佐藤組）", status: "warning", detail: "支払期日が納品後75日に設定。60日ルール抵触の可能性", checkedAt: "2026/05/12", checker: "田中 太郎" },
  { id: "cl4", law: "建設業法", item: "第26条 — 主任技術者の配置", target: "東名高速道路補修工事", status: "ng", detail: "主任技術者の配置届が未提出", checkedAt: "2026/05/12", checker: "佐藤 一郎" },
  { id: "cl5", law: "労働安全衛生法", item: "第30条 — 特定元方事業者の義務", target: "新宿駅再開発工事", status: "ok", detail: "統括安全衛生責任者を選任済み", checkedAt: "2026/05/11", checker: "佐藤 一郎" },
  { id: "cl6", law: "建設業法", item: "第19条の3 — 不当な使用資材等の購入強制の禁止", target: "資材購入契約（東日本資材）", status: "warning", detail: "特定メーカー指定条項あり、該当性を要確認", checkedAt: "2026/05/10", checker: "田中 太郎" },
  { id: "cl7", law: "下請法", item: "第4条 — 書面の交付義務", target: "下請契約書（中村組）", status: "ok", detail: "3条書面の交付済みを確認", checkedAt: "2026/05/09", checker: "鈴木 花子" },
  { id: "cl8", law: "建設業法", item: "第24条の5 — 特定建設業者の下請代金の支払", target: "横浜港防波堤改修工事", status: "ok", detail: "引渡し後50日以内の支払を確認", checkedAt: "2026/05/08", checker: "田中 太郎" },
  { id: "cl9", law: "公共工事入札契約適正化法", item: "第15条 — 施工体制台帳の提出", target: "多摩川橋梁架替工事", status: "warning", detail: "二次下請の記載が不完全、要修正", checkedAt: "2026/05/07", checker: "佐藤 一郎" },
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
  { id: "CTR-2026-0001", title: "工事請負契約（大成建設工業(株)）", type: "工事請負契約", counterparty: "大成建設工業(株)", expiresAt: "2026/05/20", daysLeft: 4, autoRenew: false, guaranteePeriod: "2年", owner: "田中 太郎", riskLevel: "high" },
  { id: "CTR-2026-0002", title: "業務委託契約（鈴木土木(株)）", type: "業務委託契約", counterparty: "鈴木土木(株)", expiresAt: "2026/06/01", daysLeft: 16, autoRenew: true, guaranteePeriod: "—", owner: "鈴木 花子", riskLevel: "medium" },
  { id: "CTR-2026-0003", title: "資材購入契約（東日本資材(株)）", type: "資材購入契約", counterparty: "東日本資材(株)", expiresAt: "2026/06/15", daysLeft: 30, autoRenew: false, guaranteePeriod: "—", owner: "佐藤 一郎", riskLevel: "low" },
  { id: "CTR-2026-0004", title: "下請契約（(株)佐藤組）", type: "下請契約", counterparty: "(株)佐藤組", expiresAt: "2026/07/01", daysLeft: 46, autoRenew: true, guaranteePeriod: "2年", owner: "山田 美咲", riskLevel: "medium" },
  { id: "CTR-2026-0005", title: "設計監理契約（(株)山田設計事務所）", type: "設計監理契約", counterparty: "(株)山田設計事務所", expiresAt: "2026/08/01", daysLeft: 77, autoRenew: false, guaranteePeriod: "—", owner: "高橋 健二", riskLevel: "low" },
  { id: "CTR-2026-0006", title: "賃貸借契約（関東リース(株)）", type: "賃貸借契約", counterparty: "関東リース(株)", expiresAt: "2026/09/01", daysLeft: 108, autoRenew: true, guaranteePeriod: "—", owner: "伊藤 直美", riskLevel: "low" },
  { id: "CTR-2026-0007", title: "秘密保持契約（東京法律事務所）", type: "秘密保持契約", counterparty: "東京法律事務所", expiresAt: "2026/11/01", daysLeft: 169, autoRenew: false, guaranteePeriod: "—", owner: "渡辺 誠", riskLevel: "low" },
  { id: "CTR-2026-0008", title: "工事請負契約（横浜建設(株)）", type: "工事請負契約", counterparty: "横浜建設(株)", expiresAt: "2026/12/31", daysLeft: 229, autoRenew: true, guaranteePeriod: "2年", owner: "中村 裕子", riskLevel: "medium" },
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
  { id: "PTR-0001", name: "大成建設工業(株)", type: "元請", permitNumber: "国土交通大臣許可（般-2024）第010000号", permitExpiry: "2026/09/15", antiSocialCheck: "確認済", antiSocialDate: "2026/01/10", insurance: "加入済", contractCount: 8, riskLevel: "low", lastTransaction: "2026/05/10" },
  { id: "PTR-0002", name: "鈴木土木(株)", type: "元請", permitNumber: "国土交通大臣許可（般-2025）第010137号", permitExpiry: "2026/11/20", antiSocialCheck: "確認済", antiSocialDate: "2026/02/05", insurance: "加入済", contractCount: 5, riskLevel: "low", lastTransaction: "2026/05/08" },
  { id: "PTR-0003", name: "(株)山田設計事務所", type: "元請", permitNumber: "国土交通大臣許可（般-2024）第010274号", permitExpiry: "2027/03/10", antiSocialCheck: "確認済", antiSocialDate: "2026/03/15", insurance: "加入済", contractCount: 3, riskLevel: "low", lastTransaction: "2026/04/20" },
  { id: "PTR-0004", name: "東日本資材(株)", type: "元請", permitNumber: "国土交通大臣許可（般-2025）第010411号", permitExpiry: "2026/07/01", antiSocialCheck: "確認済", antiSocialDate: "2026/01/20", insurance: "加入済", contractCount: 7, riskLevel: "medium", lastTransaction: "2026/05/12" },
  { id: "PTR-0005", name: "(株)佐藤組", type: "下請（一次）", permitNumber: "東京都知事許可（般-2024）第010548号", permitExpiry: "2026/10/05", antiSocialCheck: "確認済", antiSocialDate: "2025/12/01", insurance: "加入済", contractCount: 4, riskLevel: "low", lastTransaction: "2026/04/15" },
  { id: "PTR-0006", name: "中央コンサルタント(株)", type: "下請（一次）", permitNumber: "東京都知事許可（般-2025）第010685号", permitExpiry: "2027/01/15", antiSocialCheck: "確認済", antiSocialDate: "2026/02/28", insurance: "加入済", contractCount: 2, riskLevel: "low", lastTransaction: "2026/03/20" },
  { id: "PTR-0007", name: "北関東電設(株)", type: "下請（一次）", permitNumber: "埼玉県知事許可（般-2024）第010822号", permitExpiry: "2026/08/20", antiSocialCheck: "確認済", antiSocialDate: "2026/01/05", insurance: "加入済", contractCount: 6, riskLevel: "medium", lastTransaction: "2026/05/01" },
  { id: "PTR-0008", name: "(株)高橋建材", type: "下請（一次）", permitNumber: "神奈川県知事許可（般-2025）第010959号", permitExpiry: "2027/02/28", antiSocialCheck: "確認済", antiSocialDate: "2026/03/01", insurance: "加入済", contractCount: 3, riskLevel: "low", lastTransaction: "2026/04/08" },
  { id: "PTR-0009", name: "西部工業(株)", type: "下請（二次）", permitNumber: "千葉県知事許可（般-2023）第011096号", permitExpiry: "2026/06/10", antiSocialCheck: "確認済", antiSocialDate: "2025/11/15", insurance: "加入済", contractCount: 1, riskLevel: "low", lastTransaction: "2026/03/15" },
  { id: "PTR-0010", name: "(株)渡辺設備", type: "下請（二次）", permitNumber: "群馬県知事許可（般-2024）第011233号", permitExpiry: "2026/05/30", antiSocialCheck: "未確認", antiSocialDate: null, insurance: "未確認", contractCount: 2, riskLevel: "high", lastTransaction: "2026/04/30" },
  { id: "PTR-0011", name: "太平洋セメント(株)", type: "下請（二次）", permitNumber: "国土交通大臣許可（般-2025）第011370号", permitExpiry: "2027/04/15", antiSocialCheck: "確認済", antiSocialDate: "2026/04/01", insurance: "加入済", contractCount: 1, riskLevel: "low", lastTransaction: "2026/02/10" },
  { id: "PTR-0012", name: "(株)田中工務店", type: "下請（二次）", permitNumber: "東京都知事許可（般-2024）第011507号", permitExpiry: "2026/09/30", antiSocialCheck: "確認済", antiSocialDate: "2026/03/20", insurance: "加入済", contractCount: 1, riskLevel: "low", lastTransaction: "2026/01/25" },
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
  { id: "DSP-2026-0001", type: "工期遅延", title: "工期延長に伴う追加費用 — 東名高速補修", counterparty: "大成建設工業(株)", status: "open", amount: 15000000, registeredAt: "2026/04/01", assignee: "田中 太郎", priority: "高", description: "工期延長に伴う追加費用の請求。発注者との費用分担について協議中。" },
  { id: "DSP-2026-0002", type: "追加工事費用", title: "施工品質に関する是正要求 — 新宿駅再開発", counterparty: "鈴木土木(株)", status: "escalated", amount: 8000000, registeredAt: "2026/04/10", assignee: "鈴木 花子", priority: "高", description: "施工品質に関する是正要求。顧問弁護士と対応方針を協議。" },
  { id: "DSP-2026-0003", type: "品質不良", title: "近隣住民からの騒音苦情 — 横浜港防波堤", counterparty: "(株)山田設計事務所", status: "investigating", amount: 2500000, registeredAt: "2026/04/20", assignee: "佐藤 一郎", priority: "中", description: "近隣住民からの騒音苦情。防音対策の実施と補償交渉を並行して進める。" },
  { id: "DSP-2026-0004", type: "近隣クレーム", title: "下請代金の支払条件 — 多摩川橋梁", counterparty: "東日本資材(株)", status: "open", amount: null, registeredAt: "2026/04/25", assignee: "田中 太郎", priority: "中", description: "下請代金の支払条件に関する協議。60日ルール遵守を確認中。" },
  { id: "DSP-2026-0005", type: "下請トラブル", title: "追加工事費用負担 — 首都圏トンネル", counterparty: "(株)佐藤組", status: "resolved", amount: 5000000, registeredAt: "2026/03/15", assignee: "鈴木 花子", priority: "中", description: "追加工事の費用負担に関する紛争。2026/05/10に和解合意。" },
  { id: "DSP-2026-0006", type: "未払い・支払遅延", title: "工事遅延による損害賠償 — 品川再開発", counterparty: "中央コンサルタント(株)", status: "investigating", amount: null, registeredAt: "2026/03/01", assignee: "佐藤 一郎", priority: "低", description: "工事遅延による損害賠償請求。過失割合を調査中。" },
  { id: "DSP-2026-0007", type: "工期遅延", title: "品質検査不合格による手戻り — 渋谷地下道", counterparty: "北関東電設(株)", status: "resolved", amount: 1200000, registeredAt: "2026/02/20", assignee: "渡辺 誠", priority: "低", description: "品質検査不合格による手戻り費用の分担について解決済み。" },
  { id: "DSP-2026-0008", type: "未払い・支払遅延", title: "支払遅延に対する督促 — 大手町ビル", counterparty: "(株)高橋建材", status: "open", amount: 3500000, registeredAt: "2026/04/30", assignee: "田中 太郎", priority: "低", description: "支払遅延に対する督促。支払計画書の提出を依頼中。" },
];
