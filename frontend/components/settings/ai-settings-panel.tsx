"use client";

/**
 * AI settings panel (Admin settings > AI settings).
 *
 * Manages provider keys for the approved hybrid AI review architecture:
 *   (1) Perplexity Sonar  ... contract-research agent (web-grounded, live from day one)
 *   (2)/(3) DeepSeek      ... contract-reading/summary & issue-drafting agents (Claude 代替)
 *
 * Security policy (fail-closed):
 *   - API keys are never stored as plaintext in the DB (Fernet-encrypted on the backend).
 *   - Responses never carry the plaintext key; only the masked form (key_masked) is received.
 *   - On a successful save the local-state plaintext key is cleared immediately (no round-trip path).
 *   - "Connection test" probes with the stored key only (never with unsaved input).
 *
 * The final legal judgment is made by a human (legal staff / advising attorney);
 * AI output stays a draft/working proposal only.
 */

import { useMemo, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  KeyRound,
  Loader2,
  Moon,
  RotateCw,
} from "lucide-react";

import {
  ApiError,
  queryKeys,
  settingsApi,
  type AiProvider,
  type AiProviderConfig,
  type AiSettingsUpdate,
  type ConnectionTestStatus,
} from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/toaster";

// ---------------------------------------------------------------------------
// Provider display metadata
// ---------------------------------------------------------------------------

interface ProviderMeta {
  label: string;
  agentRole: string;
  description: string;
  keyPlaceholder: string;
  modelPlaceholder: string;
  /** When set, render a notice that the provider is unavailable (dormant). */
  gatedNotice?: string;
}

const PROVIDER_META: Record<AiProvider, ProviderMeta> = {
  perplexity: {
    label: "Perplexity Sonar",
    agentRole: "① 契約リサーチ Agent（Web グラウンディング）",
    description:
      "公的ソース（e-Gov 法令検索 / 国交省 / 裁判所）に限定して出典トレイルを残します。機密の契約本文は送信せず、抽象化した論点・キーワードのみを送ります。",
    keyPlaceholder: "pplx-xxxxxxxxxxxxxxxx",
    modelPlaceholder: "sonar",
  },
  deepseek: {
    label: "DeepSeek",
    agentRole: "② 契約読解・要約 / ③ 論点整理・文案 Agent",
    description:
      "機密本文を扱う前に PII マスキングを行います。出力は必ず「草案・たたき台」ラベル付きで、最終判断は法務・顧問弁護士が行います。",
    keyPlaceholder: "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    modelPlaceholder: "deepseek-chat",
  },
  claude: {
    label: "Anthropic Claude（旧）",
    agentRole: "（設定画面では非表示）",
    description: "DeepSeek への移行に伴い、MVP の設定画面では表示しません。",
    keyPlaceholder: "sk-ant-xxxxxxxxxxxxxxxx",
    modelPlaceholder: "claude-opus-4-7",
  },
};

/** Display order (Perplexity research agent first, then the DeepSeek review agents). */
const PROVIDER_ORDER: readonly AiProvider[] = ["perplexity", "deepseek"];

function emptyConfig(provider: AiProvider): AiProviderConfig {
  return {
    provider,
    has_key: false,
    key_masked: null,
    model: null,
    is_active: false,
    last_test_status: null,
    last_test_message: null,
    last_tested_at: null,
    updated_at: null,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function describeError(err: unknown): { title: string; description: string } {
  if (err instanceof ApiError) {
    if (err.isForbidden()) {
      return {
        title: "権限がありません",
        description: "AI 設定の変更は管理者のみ実行できます。",
      };
    }
    if (err.isUnauthorized()) {
      return {
        title: "認証が必要です",
        description: "セッションが切れています。再ログインしてください。",
      };
    }
    if (err.isValidationError()) {
      return {
        title: "入力値が不正です",
        description: "API キーまたはモデル名の形式を確認してください。",
      };
    }
    if (err.isTransportError()) {
      return {
        title: "サーバに接続できません",
        description: "ネットワークまたはバックエンドの状態を確認してください。",
      };
    }
    return { title: "エラーが発生しました", description: err.message };
  }
  return {
    title: "エラーが発生しました",
    description: err instanceof Error ? err.message : "不明なエラーです。",
  };
}

const TEST_STATUS_LABEL: Record<ConnectionTestStatus, string> = {
  ok: "疎通 OK",
  failed: "失敗",
  unavailable: "利用不可（休眠中）",
};

function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("ja-JP", { hour12: false });
}

function TestStatusBadge({ status }: { status: ConnectionTestStatus | null | undefined }) {
  if (status === "ok") {
    return (
      <Badge variant="default" className="gap-1 bg-emerald-600 text-xs hover:bg-emerald-600">
        <CheckCircle2 className="h-3 w-3" aria-hidden />
        {TEST_STATUS_LABEL.ok}
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge variant="destructive" className="gap-1 text-xs">
        <AlertCircle className="h-3 w-3" aria-hidden />
        {TEST_STATUS_LABEL.failed}
      </Badge>
    );
  }
  if (status === "unavailable") {
    return (
      <Badge variant="secondary" className="gap-1 text-xs">
        <Moon className="h-3 w-3" aria-hidden />
        {TEST_STATUS_LABEL.unavailable}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-xs">
      未テスト
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// Provider card (one provider = one form)
// ---------------------------------------------------------------------------

function ProviderCard({ config }: { config: AiProviderConfig }) {
  const meta = PROVIDER_META[config.provider];
  const queryClient = useQueryClient();

  // Local form state (plaintext key is cleared immediately on successful save)
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(config.model ?? "");
  const [isActive, setIsActive] = useState(config.is_active);

  const trimmedKey = apiKey.trim();
  const trimmedModel = model.trim();

  const isDirty =
    trimmedKey.length > 0 ||
    trimmedModel !== (config.model ?? "") ||
    isActive !== config.is_active;

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.settings.aiSettings() });

  const saveMutation = useMutation({
    mutationFn: (body: AiSettingsUpdate) =>
      settingsApi.updateAiProvider(config.provider, body),
    onSuccess: () => {
      setApiKey(""); // Immediately discard plaintext key from local state
      invalidate();
      toast({
        title: "保存しました",
        description: `${meta.label} の設定を更新しました。`,
      });
    },
    onError: (err) => {
      const { title, description } = describeError(err);
      toast({ title, description, variant: "destructive" });
    },
  });

  const testMutation = useMutation({
    mutationFn: () => settingsApi.testAiProvider(config.provider),
    onSuccess: (res) => {
      invalidate();
      toast({
        title: `設定テスト: ${TEST_STATUS_LABEL[res.status]}`,
        description: res.message,
        variant: res.status === "failed" ? "destructive" : undefined,
      });
    },
    onError: (err) => {
      const { title, description } = describeError(err);
      toast({ title, description, variant: "destructive" });
    },
  });

  const busy = saveMutation.isPending || testMutation.isPending;

  function handleSave() {
    const body: AiSettingsUpdate = { is_active: isActive };
    if (trimmedModel) body.model = trimmedModel;
    if (trimmedKey) body.api_key = trimmedKey; // Empty = keep existing (omit from body)
    saveMutation.mutate(body);
  }

  function handleClearKey() {
    // Explicit clear (sending empty string deletes the encrypted key)
    saveMutation.mutate({ is_active: isActive, api_key: "" });
  }

  const keyFieldId = `ai-key-${config.provider}`;
  const modelFieldId = `ai-model-${config.provider}`;
  const lastTestedAt = formatTimestamp(config.last_tested_at);

  return (
    <section className="rounded-lg border p-4">
      {/* Header: label + agent role + current status badges */}
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-muted-foreground" aria-hidden />
            <h3 className="text-sm font-semibold text-foreground">{meta.label}</h3>
          </div>
          <p className="text-xs text-muted-foreground">{meta.agentRole}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant={config.is_active ? "default" : "secondary"} className="text-xs">
            {config.is_active ? "有効" : "無効"}
          </Badge>
          <Badge variant={config.has_key ? "default" : "outline"} className="text-xs">
            {config.has_key ? "キー登録済み" : "キー未登録"}
          </Badge>
          <TestStatusBadge status={config.last_test_status} />
        </div>
      </div>

      <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{meta.description}</p>

      {/* Dormant notice (Claude is unavailable until 2026-07-01) */}
      {meta.gatedNotice ? (
        <Alert className="mt-3 border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200">
          <Moon className="h-4 w-4" aria-hidden />
          <AlertTitle className="text-xs font-semibold">利用開始前（休眠中）</AlertTitle>
          <AlertDescription className="text-xs">{meta.gatedNotice}</AlertDescription>
        </Alert>
      ) : null}

      {/* API key input */}
      <div className="mt-4 space-y-1.5">
        <Label htmlFor={keyFieldId} className="text-xs">
          API キー
        </Label>
        <Input
          id={keyFieldId}
          type="password"
          autoComplete="off"
          spellCheck={false}
          value={apiKey}
          disabled={busy}
          placeholder={
            config.has_key
              ? `${config.key_masked ?? "登録済み"}（変更する場合のみ入力）`
              : meta.keyPlaceholder
          }
          onChange={(e) => setApiKey(e.target.value)}
        />
        <p className="text-[11px] text-muted-foreground">
          {config.has_key
            ? "空欄のまま保存すると既存のキーを維持します。平文では DB に保存されません（暗号化）。"
            : "キーは保存時に暗号化され、平文では保存・表示されません。"}
        </p>
      </div>

      {/* Model name */}
      <div className="mt-3 space-y-1.5">
        <Label htmlFor={modelFieldId} className="text-xs">
          モデル
        </Label>
        <Input
          id={modelFieldId}
          type="text"
          autoComplete="off"
          spellCheck={false}
          value={model}
          disabled={busy}
          placeholder={meta.modelPlaceholder}
          onChange={(e) => setModel(e.target.value)}
        />
      </div>

      {/* Active/inactive toggle (using Button toggle since Switch component not yet available) */}
      <div className="mt-3 flex items-center justify-between gap-2">
        <div>
          <Label className="text-xs">この Agent を有効化</Label>
          <p className="text-[11px] text-muted-foreground">
            無効にすると保存しても Agent は呼び出されません。
          </p>
        </div>
        <Button
          type="button"
          variant={isActive ? "default" : "outline"}
          size="sm"
          disabled={busy}
          aria-pressed={isActive}
          onClick={() => setIsActive((v) => !v)}
        >
          {isActive ? "有効" : "無効"}
        </Button>
      </div>

      {/* Latest test result detail */}
      {(config.last_test_message || lastTestedAt) ? (
        <p className="mt-3 text-[11px] text-muted-foreground">
          直近テスト: {config.last_test_message ?? "—"}
          {lastTestedAt ? `（${lastTestedAt}）` : ""}
        </p>
      ) : null}

      {/* Action buttons */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" onClick={handleSave} disabled={busy || !isDirty}>
          {saveMutation.isPending ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : null}
          保存・設定
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => testMutation.mutate()}
          disabled={busy || isDirty}
          title={isDirty ? "先に保存してください" : undefined}
        >
          {testMutation.isPending ? (
            <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <RotateCw className="mr-1 h-3.5 w-3.5" aria-hidden />
          )}
          設定テスト
        </Button>
        {config.has_key ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="text-destructive hover:text-destructive"
            onClick={handleClearKey}
            disabled={busy}
          >
            キーを削除
          </Button>
        ) : null}
        {isDirty ? (
          <span className="text-[11px] text-amber-600 dark:text-amber-400">
            未保存の変更があります
          </span>
        ) : null}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Panel body
// ---------------------------------------------------------------------------

export function AiSettingsPanel() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: queryKeys.settings.aiSettings(),
    queryFn: () => settingsApi.getAiSettings(),
  });

  const orderedConfigs = useMemo(() => {
    const byProvider = new Map(
      (data?.providers ?? []).map((p) => [p.provider, p] as const),
    );
    return PROVIDER_ORDER.map((p) => byProvider.get(p) ?? emptyConfig(p));
  }, [data]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-48 w-full rounded-lg" />
        <Skeleton className="h-48 w-full rounded-lg" />
      </div>
    );
  }

  if (isError) {
    const { title, description } = describeError(error);
    const forbidden = error instanceof ApiError && error.isForbidden();
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" aria-hidden />
        <AlertTitle>{forbidden ? "アクセス権がありません" : title}</AlertTitle>
        <AlertDescription className="space-y-2">
          <p>
            {forbidden
              ? "AI 設定は管理者ロールのユーザのみ閲覧・変更できます。"
              : description}
          </p>
          {!forbidden ? (
            <Button type="button" size="sm" variant="outline" onClick={() => refetch()}>
              <RotateCw className="mr-1 h-3.5 w-3.5" aria-hidden />
              再読み込み
            </Button>
          ) : null}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs leading-relaxed text-muted-foreground">
          ハイブリッド AI レビュー構成の各 Agent が利用する API キーを設定します。
          キーは暗号化して保存され、平文では表示されません。すべての変更は監査ログに記録されます。
        </p>
        {isFetching ? (
          <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-muted-foreground" aria-hidden />
        ) : null}
      </div>

      {orderedConfigs.map((config) => (
        <ProviderCard key={config.provider} config={config} />
      ))}

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        ※ AI の出力はすべて「草案・たたき台」です。最終的な法的判断は法務担当者・顧問弁護士が行ってください。
      </p>
    </div>
  );
}

export default AiSettingsPanel;
