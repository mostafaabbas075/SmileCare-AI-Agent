"use client";

export default function TypingIndicator() {
  return (
    <div
      className="flex w-full items-end gap-3 animate-fade-in"
      role="status"
      aria-label="المساعد يكتب..."
      aria-live="polite"
    >
      {/* AI Avatar */}
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-2xl bg-blue-600 shadow-md shadow-blue-100">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-4 w-4"
          aria-hidden="true"
        >
          <path
            d="M9 2C7.34 2 5 3.5 5 6.5C5 9 4.5 13 4 15.5C3.5 18 4 22 6 22C7.5 22 8 19.5 9 17.5C9.5 16.5 10.5 16 12 16C13.5 16 14.5 16.5 15 17.5C16 19.5 16.5 22 18 22C20 22 20.5 18 20 15.5C19.5 13 19 9 19 6.5C19 3.5 16.66 2 15 2C13.5 2 12.5 3 12 3C11.5 3 10.5 2 9 2Z"
            fill="white"
            strokeWidth="0.5"
          />
        </svg>
      </div>

      {/* Dots bubble */}
      <div className="flex items-center gap-1.5 rounded-2xl rounded-ss-sm border border-slate-100 bg-white px-4 py-3.5 shadow-sm">
        <span
          className="animate-bounce-dot h-2 w-2 rounded-full bg-slate-300"
          style={{ animationDelay: "0ms" }}
        />
        <span
          className="animate-bounce-dot h-2 w-2 rounded-full bg-slate-300"
          style={{ animationDelay: "180ms" }}
        />
        <span
          className="animate-bounce-dot h-2 w-2 rounded-full bg-slate-300"
          style={{ animationDelay: "360ms" }}
        />
      </div>
    </div>
  );
}
