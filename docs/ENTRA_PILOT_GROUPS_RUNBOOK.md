# 👥 Entra ID パイロットグループ作成手順書（P-7）

> 実行は **Microsoft Entra ID 管理者** が行う。本手順書はパイロット展開（法務部門 5〜10 名）用。

## 📋 1. 作成するグループ

| グループ名 | 対象 | ロール割当 |
| --- | --- | --- |
| `LegalOps-Pilot-Admin` | IT/DX 1 名 + 法務 DX 担当 | admin |
| `LegalOps-Pilot-Legal` | 法務リード 1・レビュー担当 3〜5 | legal / reviewer |
| `LegalOps-Pilot-Manager` | 管理部門 1 名 | manager |
| `LegalOps-Pilot-Auditor` | 内部監査 1 名 | auditor |

## 🔧 2. 作成コマンド（Microsoft Graph PowerShell）

```powershell
Connect-MgGraph -Scopes "Group.ReadWrite.All", "User.Read.All"

$groups = @(
  @{ Name = "LegalOps-Pilot-Admin";   Description = "LegalOps パイロット管理者（IT/DX）" },
  @{ Name = "LegalOps-Pilot-Legal";   Description = "LegalOps パイロット法務（レビュー担当）" },
  @{ Name = "LegalOps-Pilot-Manager"; Description = "LegalOps パイロット管理部門" },
  @{ Name = "LegalOps-Pilot-Auditor"; Description = "LegalOps パイロット監査" }
)

foreach ($g in $groups) {
  $body = @{
    displayName     = $g.Name
    description     = $g.Description
    mailEnabled     = $false
    mailNickname    = $g.Name.Replace("-", "")
    securityEnabled = $true
  }
  New-MgGroup -BodyParameter $body
}
```

## 🔧 3. メンバー追加

```powershell
# 例: 法務担当を Legal グループへ追加
$group = Get-MgGroup -Filter "displayName eq 'LegalOps-Pilot-Legal'"
$user  = Get-MgUser -Filter "mail eq 'hanako.suzuki@example.co.jp'"
New-MgGroupMember -GroupId $group.Id -DirectoryObjectId $user.Id
```

## 🔧 4. アプリへの割当と検証

1. Entra ID のアプリ登録（本システム）で「ユーザーとグループ」へ上記 4 グループを追加
2. Cloudflare Access の Access Group に Entra グループをマッピング（SAML/SCIM 連携時）
3. 検証:
   - パイロットユーザーでログインし `/api/v1/auth/me` の `role` が期待どおり
   - 誤割当がないか監査ログ（`GET /audit-logs`）で確認
   - 四半期ごとにグループメンバーをレビュー

## ✅ 5. 完了条件

- [ ] 4 グループ作成・メンバー割当完了
- [ ] アプリ割当とロールマッピング反映
- [ ] パイロットユーザーのログイン・ロール確認成功
- [ ] メンバー変更履歴が Entra ID 監査ログに記録
