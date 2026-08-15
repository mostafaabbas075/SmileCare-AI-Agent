"use client";

import QuickActions from "./QuickActions";

interface WelcomeScreenProps {
  onSelectQuestion: (text: string) => void;
}

export default function WelcomeScreen({ onSelectQuestion }: WelcomeScreenProps) {
  return (
    <div
      className="flex flex-1 flex-col items-center justify-center px-6 py-12 text-center animate-fade-in"
      role="main"
      aria-label="شاشة الترحيب"
    >
      {/* Hero icon */}
      <div className="relative mb-6 animate-slide-up">
        <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-blue-500 to-blue-700 shadow-xl shadow-blue-200/60">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="h-10 w-10"
            aria-hidden="true"
          >
            <path
              d="M9 2C7.34 2 5 3.5 5 6.5C5 9 4.5 13 4 15.5C3.5 18 4 22 6 22C7.5 22 8 19.5 9 17.5C9.5 16.5 10.5 16 12 16C13.5 16 14.5 16.5 15 17.5C16 19.5 16.5 22 18 22C20 22 20.5 18 20 15.5C19.5 13 19 9 19 6.5C19 3.5 16.66 2 15 2C13.5 2 12.5 3 12 3C11.5 3 10.5 2 9 2Z"
              fill="white"
              strokeWidth="0.5"
            />
          </svg>
        </div>

        {/* Subtle glow ring */}
        <div
          className="absolute inset-0 rounded-3xl bg-blue-400 opacity-20 blur-xl scale-110"
          aria-hidden="true"
        />
      </div>

      {/* Heading */}
      <h2 className="text-2xl font-bold text-slate-800 tracking-tight animate-slide-up">
        مرحباً بك في SmileCare
      </h2>

      {/* Subtitle */}
      <p className="mt-2 max-w-xs text-sm text-slate-500 leading-relaxed animate-slide-up-delayed">
        مساعدك الذكي لحجز المواعيد والاستفسار عن خدمات عيادة الأسنان على مدار
        الساعة
      </p>

      {/* Divider */}
      <div className="mt-8 flex items-center gap-3 w-full max-w-xs">
        <div className="flex-1 h-px bg-slate-100" />
        <span className="text-xs text-slate-400 font-medium">ابدأ بسؤال</span>
        <div className="flex-1 h-px bg-slate-100" />
      </div>

      {/* Quick-action chips */}
      <QuickActions onSelect={onSelectQuestion} />
    </div>
  );
}
