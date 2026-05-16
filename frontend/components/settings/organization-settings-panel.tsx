const ORG = {
  name: "株式会社建設法務DX",
  code: "CONST-LEGAL-DX",
  plan: "Enterprise",
  adminEmail: "admin@const-legal-dx.example",
  timezone: "Asia/Tokyo",
  locale: "ja-JP",
};

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-3 gap-4 py-3 border-b last:border-0">
      <dt className="text-sm font-medium text-muted-foreground">{label}</dt>
      <dd className="col-span-2 text-sm">{value}</dd>
    </div>
  );
}

export function OrganizationSettingsPanel() {
  return (
    <dl>
      <Row label="組織名" value={ORG.name} />
      <Row label="組織コード" value={ORG.code} />
      <Row label="プラン" value={ORG.plan} />
      <Row label="管理者メール" value={ORG.adminEmail} />
      <Row label="タイムゾーン" value={ORG.timezone} />
      <Row label="ロケール" value={ORG.locale} />
    </dl>
  );
}
export default OrganizationSettingsPanel;
