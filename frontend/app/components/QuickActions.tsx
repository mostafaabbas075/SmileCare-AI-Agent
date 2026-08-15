"use client";

type QuickAction = {
  id: string;
  label: string;
  icon: string;
  text: string;
};

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: "book",
    label: "حجز موعد",
    icon: "📅",
    text: "أريد حجز موعد في العيادة",
  },
  {
    id: "whitening",
    label: "تبييض الأسنان",
    icon: "✨",
    text: "ما هي تفاصيل خدمة تبييض الأسنان؟",
  },
  {
    id: "implants",
    label: "زراعة الأسنان",
    icon: "🦷",
    text: "ما هي تفاصيل وتكلفة زراعة الأسنان؟",
  },
  {
    id: "prices",
    label: "الأسعار",
    icon: "💰",
    text: "ما هي أسعار خدماتكم؟",
  },
];

interface QuickActionsProps {
  onSelect: (text: string) => void;
}

export default function QuickActions({ onSelect }: QuickActionsProps) {
  return (
    <div
      className="flex flex-wrap justify-center gap-2.5 mt-6 animate-slide-up-delayed"
      role="group"
      aria-label="أسئلة مقترحة"
    >
      {QUICK_ACTIONS.map((action) => (
        <button
          key={action.id}
          id={`quick-action-${action.id}`}
          onClick={() => onSelect(action.text)}
          className="group flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-600 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 hover:shadow-md hover:shadow-blue-100 active:translate-y-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          aria-label={`اسأل عن: ${action.label}`}
        >
          <span className="text-base leading-none">{action.icon}</span>
          <span>{action.label}</span>
        </button>
      ))}
    </div>
  );
}
