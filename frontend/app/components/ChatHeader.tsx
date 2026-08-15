"use client";

export default function ChatHeader() {
  return (
    <header
      className="flex items-center justify-between px-5 py-4 bg-white border-b border-slate-100"
      role="banner"
      aria-label="SmileCare AI Header"
    >
      {/* Brand */}
      <div className="flex items-center gap-3">
        {/* Tooth icon */}
        <div
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-2xl bg-blue-600 shadow-md shadow-blue-200"
          aria-hidden="true"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
            aria-hidden="true"
          >
            <path
              d="M9 2C7.34 2 5 3.5 5 6.5C5 9 4.5 13 4 15.5C3.5 18 4 22 6 22C7.5 22 8 19.5 9 17.5C9.5 16.5 10.5 16 12 16C13.5 16 14.5 16.5 15 17.5C16 19.5 16.5 22 18 22C20 22 20.5 18 20 15.5C19.5 13 19 9 19 6.5C19 3.5 16.66 2 15 2C13.5 2 12.5 3 12 3C11.5 3 10.5 2 9 2Z"
              fill="white"
              stroke="white"
              strokeWidth="0.5"
              strokeLinejoin="round"
            />
          </svg>
        </div>

        {/* Title block */}
        <div>
          <h1 className="text-base font-semibold text-slate-800 leading-tight tracking-tight">
            SmileCare AI
          </h1>
          <p className="text-xs text-slate-500 leading-none mt-0.5">
            مساعد الاستقبال الذكي
          </p>
        </div>
      </div>

      {/* Online status */}
      <div
        className="flex items-center gap-2"
        aria-label="حالة المساعد: متصل"
        role="status"
      >
        <span className="text-xs text-slate-400 font-medium">متصل الآن</span>
        <div className="relative flex h-3 w-3 items-center justify-center">
          <span className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
        </div>
      </div>
    </header>
  );
}
