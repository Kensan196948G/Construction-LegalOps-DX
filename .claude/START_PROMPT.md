/goal
"CLAUDE.mdを恒久指示として全て読み、CTO代行として本リポジトリを再調査してください。Cloudflare・Neonの設定と認証は完了済みです。GitHubを含む対象account／project／environmentをread-onlyで確認し、既存設定を使用してください。
Monitor → Plan → Development → Verify → Review → Improvementを、CLAUDE.mdのPhase 1完了条件を全て満たすまで自律的に繰り返してください。
今回はPhase 1で、実装・テスト・文書更新に加え、Neon development／preview branchでのmigration・接続確認、Cloudflare非本番previewへの実デプロイ、Access・主要画面・API・DB・ログ・secret露出のデプロイ後確認を必須とします。問題は修正・再検証・再デプロイしてください。
致命的blocker以外では質問で停止せず、作業branch作成、commit、push、CI成功、PR作成・更新、`gh pr merge --auto --squash`による自動マージ予約まで進めてください（マージ条件はRequired Checksの全成功とmerge conflictがないことだけで、人間のY/N・Approveを待たず、`--admin`は使わない）。Phase 1完了時に結果とproduction-safe判定を報告し、本番リリースのHuman Gateとして「本番リリース判定：Y / N」を求めてください。Y後はCLAUDE.mdのPhase 2に従い、production deployment、smoke test、監視、必要時rollback、最終報告まで自律実行してください。"