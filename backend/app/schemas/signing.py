"""電子署名エンベロープの API スキーマ."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SigningMethod, SigningProviderId


class SigningEnvelopeCreate(BaseModel):
    """署名エンベロープの作成要求."""

    contract_id: int = Field(..., description="対象契約の内部 id")
    method: SigningMethod = Field(
        default=SigningMethod.ELECTRONIC,
        description="electronic=電磁的方法（承諾証跡必須）/ paper=書面",
    )
    provider: SigningProviderId = Field(
        default=SigningProviderId.DEMO,
        description="cloudsign / docusign / demo / manual（demo 既定）",
    )
    counterparty_name: str | None = Field(default=None, max_length=255)
    counterparty_email: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, description="依頼・添付メモ")


class SigningConsentIn(BaseModel):
    """相手方の承諾証跡（建設業法 19 条・電磁的方法による交付の承諾）."""

    consentor_name: str | None = Field(default=None, max_length=255)
    consentor_email: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, description="承諾の取得経緯・方法（証跡）")


class SigningSignIn(BaseModel):
    """署名（相手方）."""

    signer_name: str | None = Field(default=None, max_length=255)
    signer_email: str | None = Field(default=None, max_length=255)


class SigningCompleteIn(BaseModel):
    """締結完了（signed → completed）.

    ``attachment_id`` 指定時は締結済み原本を正本（signed_original）として取り込む。
    """

    attachment_id: int | None = Field(default=None)


class SigningCancelIn(BaseModel):
    """エンベロープ取消."""

    reason: str | None = Field(default=None, max_length=1000)


class SigningEventOut(BaseModel):
    """証跡イベント（追記専用・読み取りのみ）."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    envelope_id: int
    event_type: str
    actor_id: int | None
    payload: dict[str, Any] | None
    created_at: datetime


class SigningEnvelopeOut(BaseModel):
    """署名エンベロープ."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    envelope_no: str
    contract_id: int
    status: str
    method: str
    provider: str
    provider_envelope_id: str | None
    counterparty_name: str | None
    counterparty_email: str | None
    note: str | None
    consent_confirmed_at: datetime | None
    consentor_name: str | None
    consentor_email: str | None
    consent_note: str | None
    sent_at: datetime | None
    viewed_at: datetime | None
    signed_at: datetime | None
    completed_at: datetime | None
    signer_name: str | None
    signer_email: str | None
    signed_attachment_id: int | None
    signed_document_id: int | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    version: int
