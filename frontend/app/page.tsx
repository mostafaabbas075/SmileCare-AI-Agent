"use client";

import { useState, useRef, useEffect } from "react";
import axios from "axios";
import { Send, User, Bot, Loader2 } from "lucide-react";

type Message = {
  id: number;
  role: "user" | "ai";
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { id: 1, role: "ai", content: "أهلاً بك في عيادة الأسنان! كيف يمكنني مساعدتك اليوم؟" }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 🧠 الحل الجذري للـ Session ID 
  const [sessionId, setSessionId] = useState("");

  // يتم استدعاء هذا الكود مرة واحدة فقط لضمان ثبات الجلسة (Session)
  useEffect(() => {
    let currentSession = sessionStorage.getItem("chat_session_id");
    if (!currentSession) {
      currentSession = `session-${Date.now()}`;
      sessionStorage.setItem("chat_session_id", currentSession);
    }
    setSessionId(currentSession);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId) return;

    const userMessage: Message = { id: Date.now(), role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await axios.post("http://localhost:8000/api/v1/chat", {
        message: userMessage.content,
        session_id: sessionId,
      });

      const aiMessage: Message = {
        id: Date.now() + 1,
        role: "ai",
        content: response.data.message || "عذراً، حدث خطأ في معالجة الرد.",
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error("Error fetching chat response:", error);
      const errorMessage: Message = {
        id: Date.now() + 1,
        role: "ai",
        content: "عذراً، لا يمكنني الاتصال بالخادم الآن. يرجى التأكد من تشغيل الباك إند بشكل صحيح.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main dir="rtl" className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-slate-100 to-slate-200 p-4 font-sans">
      <div className="flex h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-3xl border border-white/60 bg-white/40 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.1)] backdrop-blur-2xl">
        
        {/* الهيدر */}
        <div className="flex items-center justify-between border-b border-white/50 bg-white/30 px-6 py-4 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-white shadow-lg">
              <Bot size={20} />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-800">مساعد العيادة</h1>
              <p className="text-xs text-slate-500">متصل الآن ومستعد للمساعدة</p>
            </div>
          </div>
          <div className="flex h-3 w-3 items-center justify-center">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75"></span>
            <span className="relative inline-flex h-3 w-3 rounded-full bg-green-500"></span>
          </div>
        </div>

        {/* عرض الرسائل */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex w-full ${msg.role === "user" ? "justify-start" : "justify-end"}`}>
              <div className={`flex max-w-[80%] items-end gap-2 ${msg.role === "user" ? "flex-row" : "flex-row-reverse"}`}>
                
                <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full shadow-sm ${msg.role === "user" ? "bg-blue-100 text-blue-600" : "bg-slate-200 text-slate-600"}`}>
                  {msg.role === "user" ? <User size={16} /> : <Bot size={16} />}
                </div>

                <div className={`rounded-2xl px-5 py-3 text-sm leading-relaxed shadow-sm ${
                    msg.role === "user" ? "rounded-br-none bg-slate-800 text-white" : "rounded-bl-none border border-white/50 bg-white/80 text-slate-800 backdrop-blur-sm"
                  }`}>
                  {msg.content}
                </div>
              </div>
            </div>
          ))}
          
          {isLoading && (
            <div className="flex w-full justify-end">
              <div className="flex max-w-[80%] items-end gap-2 flex-row-reverse">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600 shadow-sm">
                  <Bot size={16} />
                </div>
                <div className="flex rounded-2xl rounded-bl-none border border-white/50 bg-white/80 px-5 py-4 backdrop-blur-sm">
                  <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* الإدخال */}
        <div className="border-t border-white/50 bg-white/30 p-4 backdrop-blur-md">
          <form onSubmit={handleSendMessage} className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="اكتب استفسارك هنا..."
              className="w-full rounded-full border border-slate-200 bg-white/80 py-4 pl-14 pr-6 text-sm text-slate-800 shadow-inner outline-none transition-all focus:border-slate-400 focus:ring-2 focus:ring-slate-400/20"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute left-2 flex h-10 w-10 items-center justify-center rounded-full bg-slate-800 text-white transition-transform hover:scale-105 active:scale-95 disabled:opacity-50"
            >
              <Send size={18} className="-ml-1" />
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}