import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Tailwind class merger helper.
 * Combines clsx (conditional class composition) with tailwind-merge
 * (resolves Tailwind utility conflicts).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
