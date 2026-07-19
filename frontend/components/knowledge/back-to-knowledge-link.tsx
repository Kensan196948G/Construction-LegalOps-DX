"use client";

import type { MouseEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";

interface BackToKnowledgeLinkProps {
  className?: string;
}

export function BackToKnowledgeLink({ className }: BackToKnowledgeLinkProps) {
  const router = useRouter();

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.altKey ||
      event.ctrlKey ||
      event.shiftKey
    ) {
      return;
    }

    event.preventDefault();
    router.push("/knowledge");
  }

  return (
    <Link
      href="/knowledge"
      className={className}
      data-testid="back-link"
      onClick={handleClick}
    >
      <ArrowLeft className="h-4 w-4" aria-hidden />
      ナレッジベースに戻る
    </Link>
  );
}
