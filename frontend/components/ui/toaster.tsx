"use client";

import * as React from "react";

import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
  type ToastActionElement,
  type ToastProps,
} from "@/components/ui/toast";

export type ToasterToast = ToastProps & {
  id: string;
  title?: React.ReactNode;
  description?: React.ReactNode;
  action?: ToastActionElement;
};

/**
 * Minimal toast store. Real applications should swap this for a more
 * fully-featured implementation (e.g. Sonner) or extend with reducer logic.
 */
const listeners = new Set<(toasts: ToasterToast[]) => void>();
let memoryToasts: ToasterToast[] = [];

function emit() {
  listeners.forEach((listener) => listener(memoryToasts));
}

export function toast(props: Omit<ToasterToast, "id"> & { id?: string }) {
  const id = props.id ?? Math.random().toString(36).slice(2);
  const next: ToasterToast = { ...props, id };
  memoryToasts = [next, ...memoryToasts].slice(0, 5);
  emit();
  return {
    id,
    dismiss: () => {
      memoryToasts = memoryToasts.filter((t) => t.id !== id);
      emit();
    },
  };
}

export function useToast() {
  const [toasts, setToasts] = React.useState<ToasterToast[]>(memoryToasts);
  React.useEffect(() => {
    listeners.add(setToasts);
    return () => {
      listeners.delete(setToasts);
    };
  }, []);
  return { toasts, toast };
}

export function Toaster() {
  const { toasts } = useToast();

  return (
    <ToastProvider>
      {toasts.map(({ id, title, description, action, ...props }) => (
        <Toast key={id} {...props}>
          <div className="grid gap-1">
            {title ? <ToastTitle>{title}</ToastTitle> : null}
            {description ? (
              <ToastDescription>{description}</ToastDescription>
            ) : null}
          </div>
          {action}
          <ToastClose />
        </Toast>
      ))}
      <ToastViewport />
    </ToastProvider>
  );
}
