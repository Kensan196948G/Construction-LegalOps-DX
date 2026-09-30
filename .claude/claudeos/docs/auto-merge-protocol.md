# Auto Merge Protocol — Required Checks 全成功での自動マージ

## 概要

PR は `gh pr merge --auto --squash` で自動マージを予約する。マージの条件は Required Checks の全成功と merge conflict がないことだけとし、人間の Y/N・選択・Approve を待たない（main/default branch 宛も同じ）。`--admin` による迂回は禁止する。Release・本番デプロイ・秘密情報の変更・不可逆な削除は、コードのマージとは別に Human Gate とする。（正本: 中央ポリシー `GITHUB_POLICY.md` v2）

Trust Level はマージ条件ではない（CTO の自律度の参考指標としてのみ扱う）。

---

## 発動条件

| 条件 | 内容 |
|---|---|
| Required Checks | 全成功（未完了の間は GitHub の auto-merge が待つ） |
| merge conflict | ないこと |
| 品質ゲート | Security Critical 指摘が残っていないこと（残っている間は予約しない） |

## マージとは別の Human Gate

次はマージ自体を止める条件ではなく、マージ後の**実行**に人間の承認を要する操作である。

- 本番デプロイ・Release
- 秘密情報の変更
- 不可逆な削除（destructive migration・production data 削除を含む）

---

## CTO の実行手順

```bash
# 1. auto-merge を予約（Required Checks 全成功・conflict なしで GitHub がマージする。--admin は使わない）
gh pr merge <PR番号> --auto --squash
echo "[AutoMerge] PR #<番号> に auto-merge を設定しました"

# 2. 状態を確認
gh pr checks <PR番号>
```

---

## PowerShell 版（Windows cron 環境）

```powershell
gh pr merge $prNumber --auto --squash
Write-Host "[AutoMerge] PR #$prNumber auto-merge 設定"
```

---

## 注意事項

- `--auto` フラグは「CI 通過後に自動マージ」を設定するもので、即時マージではない
- Required Checks の失敗や merge conflict を検知した場合は auto-merge を取り消し、修正・再検証後に改めて予約する:
  ```bash
  gh pr merge <PR番号> --disable-auto
  ```
- 週次で auto-merge の実績を確認し、問題があれば Required Checks を強化すること
