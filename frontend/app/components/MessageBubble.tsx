"use client";

type MessageRole = "user" | "ai";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
}

/** Render newlines and basic markdown-like bold (**text**) in message content */
function renderContent(text: string) {
  return text.split("\n").map((line, i) => {
    // Replace **bold** markers
    const parts = line.split(/\*\*(.*?)\*\*/g);
    return (
      <span key={i}>
        {parts.map((part, j) =>
          j % 2 === 1 ? (
            <strong key={j} className="font-semibold">
              {part}
            </strong>
          ) : (
            <span key={j}>{part}</span>
          )
        )}
        {i < text.split("\n").length - 1 && <br />}
      </span>
    );
  });
}

export default function MessageBubble({ role, content }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div
      className={`flex w-full items-end gap-3 animate-slide-up ${
        isUser ? "flex-row-reverse" : "flex-row"
      }`}
      role="article"
      aria-label={isUser ? "رسالتك" : "رد المساعد"}
    >
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-2xl shadow-sm ${
          isUser
            ? "bg-slate-700 text-white"
            : "bg-blue-600 shadow-md shadow-blue-100"
        }`}
        aria-hidden="true"
      >
        {isUser ? (
          /* Simple person icon */
          <svg
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            aria-hidden="true"
          >
            <circle cx="12" cy="8" r="4" fill="white" />
            <path
              d="M4 20c0-4 3.582-7 8-7s8 3 8 7"
              stroke="white"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        ) : (
          /* Tooth icon */
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
        )}
      </div>

      {/* Bubble */}
      <div
        className={`max-w-[78%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "rounded-ee-sm bg-slate-800 text-white shadow-sm"
            : "rounded-ss-sm border border-slate-100 bg-white text-slate-700 shadow-sm"
        }`}
      >
        {renderContent(content)}
      </div>
    </div>
  );
}
