"use client";
import type { ReactNode } from "react";

export function CreateTemplateButton({ children }: { children: ReactNode }) {
  return <div onClick={() => alert("ひな形作成機能は実装予定です")}>{children}</div>;
}
export default CreateTemplateButton;
