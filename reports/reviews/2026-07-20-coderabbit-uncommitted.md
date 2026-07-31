# CodeRabbit Review Evidence — Loop 108

Date: 2026-07-20
Scope: uncommitted local changes
Command: `coderabbit review --agent -t uncommitted`

## Result

- CLI: `0.6.5`
- Auth: OK
- Initial run: timed out after 300s, but returned major findings before timeout.
- Later uncommitted run: timed out after 300s, but returned additional major findings before timeout. The process was stopped after collecting findings to avoid leaving a long-running external review session active.
- Final claim: do not claim CodeRabbit Critical/High = 0. Treat CodeRabbit as partial AI review evidence plus local static/security gates.
- Final re-run: timed out after 360s on the current uncommitted diff, but returned additional findings. Valid findings were reviewed and fixed; the timeout artifact is stored at `reports/reviews/coderabbit-uncommitted-2026-07-20T-final.txt`.

## Findings And Disposition

| Area | Severity | Disposition |
|---|---:|---|
| Cloudflare helper post-check relied on public `dig CNAME`, which can be empty for proxied records | major | Fixed. Helper now validates Cloudflare API CNAME content and checks public Access challenge separately. |
| Runbook referenced Tunnel token while compose overlay requires credentials JSON file | major | Fixed. Docs, checklist, verifier, and pre-deploy compose env now use `CLOUDFLARE_TUNNEL_CREDENTIALS_FILE`. |
| Release verifier relied heavily on string checks | major | Partially accepted. Added concrete dry-run/fail-close helper checks, API CNAME guard checks, TLS stop-line guard, credentials-file checks, and targeted tests. Full verifier redesign is out of scope for the local release stop-line turn. |
| Production stop-line used `curl -k` and HTTP/2-specific matching | major | Fixed. Stop-line keeps normal TLS verification and matches generic `HTTP/x 302` plus Cloudflare Access header. |
| `CLAUDE.md` lacked explicit Critical Security Issue immediate-stop wording | major | Fixed. Critical Security Issue detection now stops normal development and prioritizes containment, RCA, impact analysis, and rollback decision. |
| `CLAUDE.md` `/goal` example lacked a fixed turn stop condition | major | Fixed. Example now includes `stop after 20 turns` and stop-report requirements. |
| `CLAUDE.md` quality gates were too conditional | major | Fixed. lint, unit, integration, build, security check, and review are mandatory gates; unavailable checks are `NOT RUN` or `BLOCKED`. |
| `CLAUDE.md` described Claude Code executing production deployment | major | Fixed. Claude Code/Supervisor/CTO are limited to deploy-ready judgment, procedure generation, and read-only post-human verification. |
| Cloudflare existing-edge and new-resource creation were ambiguous across docs | major | Fixed. README, approval packet, final report, and infra Cloudflare README separate read-only adoption of the existing `legalops.mirai-dx-platform.com` edge from new-resource creation in unapplied environments. |
| Production stop-line accepted weak Cloudflare proof | major | Fixed. Stop-line now requires Cloudflare DNS API `proxied=true` and validates redirect destination is Cloudflare Access login. |
| Cloudflare apply-helper UUID proof was string-only | major | Fixed. Cloudflare preflight mock-runs the helper in dry-run mode and proves tunnel names resolve to UUIDs before `route dns`. |
| `state.json` exposed deploy-ready semantics while human gates remained | major | Fixed. `project.status` is now `code_complete_production_approval_pending` and `deploy_ready=false` while #23/#24/#50 and PR #70 remain human gates. |
| Phase 1 / Phase 3 wording could imply approval-scope expansion after `Y` | major | Fixed. `CLAUDE.md` now requires all applicable gates to be `PASS`, keeps Phase 1 blocked on `NOT RUN` / `BLOCKED`, and limits post-release autonomous action to read-only verification plus new PR/Approval PR for out-of-scope changes. |
| Safety-critical unknowns could be filled by assumptions | major | Fixed. `CLAUDE.md` now stops on unverifiable environment/resource/credential/permission/security/data-integrity/legal-contract assumptions, unknown impact, or non-unique target identification. |
| Final stop report risk table rendered a narrative line inside the table | minor | Fixed. The Loop 94-108 narrative was moved outside the risk table. |
| Final stop report Cloudflare procedure mixed existing-edge adoption and new creation | major | Fixed. Existing-edge adoption is now read-only/no-route-change; Access/Tunnel/CNAME creation happens only in the new-creation branch. |
| README exposed fixed internal WebUI IP/port/service values | major | Fixed. README now references the access-controlled status JSON and final session report; release evidence documents retain the operational proof. |
| Release checklist pending classifier matched generic `dry-run` | minor | Fixed. The expected pattern now matches the Cloudflare Tunnel UUID resolution context. |
| Release docs internal-link validator allowed targets outside repo root | minor | Fixed. It resolves targets and rejects absolute/parent-traversal links outside the repository root. |
| nginx NextAuth regex also matched `/api/login` and `/api/token` | minor | Fixed. Both HTTP and HTTPS server blocks now route only `/api/auth(/|$)` to the frontend, leaving other `/api/` routes on the backend. |

## Verification After Fixes

- `bash scripts/verify_release_docs.sh` -> Passed 330 / Failed 0
- `bash scripts/verify_cloudflare_legalops.sh` -> Passed 46 / Failed 0 / Warnings 0
- `REQUIRED_OPEN_PRS=70 bash scripts/verify_production_stop_line.sh` -> Passed 14 / Failed 0
- `SKIP_DOCKER_BUILD=1 ./scripts/pre_deploy_check.sh` -> Passed 25 / Failed 0 / Warnings 5
- `./scripts/scan_secrets.sh` -> no high-confidence secret patterns

No production deploy, public DNS change, Cloudflare resource mutation, secret update, push, merge, release tag, or destructive migration was performed.
