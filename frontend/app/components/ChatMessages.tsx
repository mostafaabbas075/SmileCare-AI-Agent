"use client";

import { RefObject } from "react";
import MessageBubble from "./MessageBubble";
import TypingIndicator from "./TypingIndicator";

type Message = {
  id: number;
  role: "user" | "ai";
  content: string;
};

interface ChatMessagesProps {
  messages: Message[];
  isLoading: boolean;
  ref: RefObject<HTMLDivElement | null>;
}

// React 19: refs are passed as regular props (forwardRef is deprecated)
export default function ChatMessages({
  messages,
  isLoading,
  ref,
}: ChatMessagesProps) {
  return (
    <div
      className="flex-1 overflow-y-auto px-4 py-5 space-y-4"
      role="log"
      aria-label="محادثة مع المساعد"
      aria-live="polite"
      aria-relevant="additions"
    >
      {messages.map((msg) => (
        <MessageBubble key={msg.id} role={msg.role} content={msg.content} />
      ))}

      {isLoading && <TypingIndicator />}

      {/* Scroll anchor */}
      <div ref={ref} aria-hidden="true" />
    </div>
  );
}
