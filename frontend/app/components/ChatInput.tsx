"use client";

import { useRef, useEffect, KeyboardEvent, RefObject } from "react";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  isLoading: boolean;
  inputRef?: RefObject<HTMLTextAreaElement | null>;
}

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  isLoading,
  inputRef,
}: ChatInputProps) {
  const internalRef = useRef<HTMLTextAreaElement>(null);
  const textareaRef = inputRef ?? internalRef;

  /** Auto-resize textarea height */
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, [value, textareaRef]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && value.trim()) {
        onSubmit(e as unknown as React.FormEvent);
      }
    }
  };

  const canSend = !isLoading && value.trim().length > 0;

  return (
    <div className="border-t border-slate-100 bg-white px-4 py-3">
      <form
        onSubmit={onSubmit}
        className="flex items-end gap-3"
        role="form"
        aria-label="إرسال رسالة"
      >
        {/* Textarea */}
        <div className="relative flex-1">
          <textarea
            ref={textareaRef}
            id="chat-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="اكتب استفسارك هنا... (Enter للإرسال، Shift+Enter لسطر جديد)"
            disabled={isLoading}
            rows={1}
            aria-label="رسالتك"
            aria-multiline={true}
            className="w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 placeholder-slate-400 shadow-sm transition-all duration-200 outline-none focus:border-blue-400 focus:bg-white focus:ring-2 focus:ring-blue-500/10 disabled:cursor-not-allowed disabled:opacity-60"
            style={{ maxHeight: "120px", minHeight: "48px" }}
          />
        </div>

        {/* Send button */}
        <button
          type="submit"
          id="chat-send-button"
          disabled={!canSend}
          aria-label="إرسال الرسالة"
          className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl shadow-md transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
            canSend
              ? "bg-blue-600 text-white shadow-blue-200 hover:bg-blue-700 hover:scale-105 active:scale-95"
              : "bg-slate-100 text-slate-300 cursor-not-allowed shadow-none"
          }`}
        >
          {isLoading ? (
            /* Spinner */
            <svg
              className="h-5 w-5 animate-spin"
              viewBox="0 0 24 24"
              fill="none"
              aria-hidden="true"
            >
              <circle
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="3"
                strokeOpacity="0.3"
              />
              <path
                d="M12 2a10 10 0 0 1 10 10"
                stroke="currentColor"
                strokeWidth="3"
                strokeLinecap="round"
              />
            </svg>
          ) : (
            /* Send icon (RTL-mirrored) */
            <svg
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              aria-hidden="true"
            >
              <path
                d="M22 2L11 13"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M22 2L15 22L11 13L2 9L22 2Z"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </button>
      </form>

      {/* Helper hint */}
      <p className="mt-1.5 text-center text-xs text-slate-400">
        Enter للإرسال · Shift+Enter لسطر جديد
      </p>
    </div>
  );
}
