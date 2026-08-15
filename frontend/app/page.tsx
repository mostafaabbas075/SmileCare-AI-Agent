'use client';

import React, { useState, useRef, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import axios from 'axios';

type Message = {
  id: number;
  role: 'user' | 'ai';
  content: string;
  time: string;
};

type ClinicBranding = {
  logo_url?: string | null;
  primary_color: string;
  welcome_message: string;
  gps_url?: string | null;
};

type ClinicInfo = {
  id: string;
  name: string;
  slug: string;
  phone?: string | null;
  address?: string | null;
  branding: ClinicBranding;
  opening_time: string;
  closing_time: string;
};

function ChatComponent() {
  const searchParams = useSearchParams();
  // 1. قراءة الـ slug من الرابط تلقائياً (مثال: ?clinic=al-nour أو ?clinic=white)
  const clinicSlug = searchParams.get('clinic') || '';

  const [clinic, setClinic] = useState<ClinicInfo | null>(null);
  const [clinicNotFound, setClinicNotFound] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isPageLoading, setIsPageLoading] = useState(true);
  const [sessionId, setSessionId] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const apiBase =
    process.env.NEXT_PUBLIC_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://127.0.0.1:8000';

  // 2. جلب بيانات وهوية العيادة تلقائياً بمجرد فتح الرابط مع التحقق من وجودها
  useEffect(() => {
    async function fetchClinicInfo() {
      if (!clinicSlug) {
        setClinicNotFound(true);
        setIsPageLoading(false);
        return;
      }

      try {
        setIsPageLoading(true);
        setClinicNotFound(false);
        const res = await axios.get(`${apiBase}/api/v1/clinic/public?slug=${encodeURIComponent(clinicSlug)}`);
        setClinic(res.data);
      } catch (err: any) {
        console.error('Failed to load clinic public branding:', err);
        if (err.response?.status === 404 || err.response?.status === 400) {
          setClinicNotFound(true);
        }
      } finally {
        setIsPageLoading(false);
      }
    }
    fetchClinicInfo();
  }, [clinicSlug, apiBase]);

  // 3. إدارة جلسة المحادثة لكل عيادة على حدة
  useEffect(() => {
    if (!clinicSlug) return;
    let currentSession = sessionStorage.getItem(`chat_session_${clinicSlug}`);
    if (!currentSession) {
      currentSession = `session-${Date.now()}`;
      sessionStorage.setItem(`chat_session_${clinicSlug}`, currentSession);
    }
    setSessionId(currentSession);
  }, [clinicSlug]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  const handleNewSession = () => {
    const newSession = `session-${Date.now()}`;
    sessionStorage.setItem(`chat_session_${clinicSlug}`, newSession);
    setSessionId(newSession);
    setMessages([]);
    setInput('');
    inputRef.current?.focus();
  };

  // 4. إرسال الرسالة مع توثيق معرف العيادة في الرابط والـ Headers والـ Body
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || input).trim();
    if (!text || !sessionId || isLoading || clinicNotFound) return;

    const timeNow = new Date().toLocaleTimeString('ar-EG', {
      hour: '2-digit',
      minute: '2-digit',
    });

    const userMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: text,
      time: timeNow,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post(
        `${apiBase}/api/v1/chat?clinic=${encodeURIComponent(clinicSlug)}`,
        {
          message: userMessage.content,
          session_id: sessionId,
          clinic_slug: clinicSlug,
          clinic_id: clinic?.id,
        },
        {
          headers: {
            'Content-Type': 'application/json',
            'x-clinic-slug': clinicSlug,
            'x-clinic-id': clinic?.id || '',
          },
        }
      );

      const aiReply =
        response.data.message ||
        response.data.response ||
        'عذراً، لم أتمكن من معالجة الرد.';

      const aiMessage: Message = {
        id: Date.now() + 1,
        role: 'ai',
        content: aiReply,
        time: new Date().toLocaleTimeString('ar-EG', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (error: any) {
      console.error('Error fetching chat response:', error);
      const errorText =
        error.response?.status === 404
          ? 'تم إيقاف أو حذف هذه العيادة من النظام.'
          : 'عذراً، تعذر الاتصال بالخادم الآن. يرجى التأكد من تشغيل الباك إند.';

      const errorMessage: Message = {
        id: Date.now() + 1,
        role: 'ai',
        content: errorText,
        time: new Date().toLocaleTimeString('ar-EG', {
          hour: '2-digit',
          minute: '2-digit',
        }),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // 5. دالة معالجة وتنسيق النصوص (تحويل الماركداون إلى خط عريض وقوائم بدون نجوم)
  const renderFormattedText = (text: string) => {
    const lines = text.split('\n');

    return lines.map((line, lineIdx) => {
      let cleanLine = line;
      let isBullet = false;

      // فحص وتحويل النقاط (* أو -) إلى نقطة أنيقة
      if (cleanLine.trim().startsWith('* ') || cleanLine.trim().startsWith('- ')) {
        isBullet = true;
        cleanLine = cleanLine.trim().replace(/^[\*\-]\s+/, '');
      }

      // تقسيم السطر لاستخراج الكلمات العريضة (**نص**) والروابط
      const tokenRegex = /(\*\*[^*]+\*\*|https?:\/\/[^\s]+)/g;
      const segments = cleanLine.split(tokenRegex);

      const renderedSegments = segments.map((seg, segIdx) => {
        // تحويل **النص** إلى خط عريض حقيقي وإخفاء النجوم
        if (seg.startsWith('**') && seg.endsWith('**')) {
          return (
            <strong key={segIdx} className="font-bold text-slate-900">
              {seg.slice(2, -2)}
            </strong>
          );
        }
        // معالجة الروابط
        if (seg.match(/^https?:\/\/[^\s]+/)) {
          return (
            <a
              key={segIdx}
              href={seg}
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold underline hover:opacity-80 transition break-all"
              style={{ color: brandColor }}
            >
              {seg}
            </a>
          );
        }
        return <span key={segIdx}>{seg}</span>;
      });

      return (
        <div key={lineIdx} className={isBullet ? 'flex items-start gap-2 my-1 pr-1' : 'min-h-[1.2rem]'}>
          {isBullet && (
            <span className="font-bold text-emerald-600 select-none">•</span>
          )}
          <div className="flex-1">{renderedSegments}</div>
        </div>
      );
    });
  };

  const brandColor = clinic?.branding?.primary_color || '#059669';
  const clinicName = clinic?.name || 'الاستقبال الطبي';
  const welcomeText = clinic?.branding?.welcome_message || `أهلاً بك في ${clinicName}`;

  if (isPageLoading) {
    return (
      <main dir="rtl" className="flex min-h-screen items-center justify-center bg-slate-100 font-sans">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-300 border-t-emerald-600" />
          <p className="text-sm font-bold text-slate-500">جاري الاتصال بالعيادة...</p>
        </div>
      </main>
    );
  }

  // شاشة حظر الشات في حال كانت العيادة محذوفة أو غير موجودة
  if (clinicNotFound || !clinic) {
    return (
      <main dir="rtl" className="flex min-h-screen items-center justify-center bg-slate-100 p-4 font-sans text-slate-800">
        <div className="flex w-full max-w-md flex-col items-center justify-center rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 text-3xl text-rose-500 border border-rose-100">
            🏥
          </div>
          <h1 className="text-lg font-extrabold text-slate-900">العيادة غير متوفرة</h1>
          <p className="mt-2 text-xs sm:text-sm text-slate-500 leading-relaxed">
            الرابط الذي تحاول الوصول إليه غير مسجل بالنظام أو تم إيقاف الخدمة لهذه العيادة.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main
      dir="rtl"
      className="flex min-h-screen items-center justify-center bg-slate-100 p-2 sm:p-4 font-sans text-slate-800"
    >
      <div
        className="flex w-full max-w-3xl flex-col overflow-hidden rounded-3xl border border-slate-200/90 bg-white shadow-xl"
        style={{ height: 'clamp(540px, 88vh, 780px)' }}
      >
        {/* ── رأس البطاقة (Header) ── */}
        <header className="flex items-center justify-between border-b border-slate-100 bg-white p-4 px-6 shrink-0">
          <div className="flex items-center gap-3">
            <div
              className="relative flex h-11 w-11 items-center justify-center rounded-2xl text-white text-xl shadow-md"
              style={{ backgroundColor: brandColor }}
            >
              {clinic?.branding?.logo_url ? (
                <img src={clinic.branding.logo_url} alt="Logo" className="h-7 w-7 object-contain" />
              ) : (
                '🦷'
              )}
              <span className="absolute -bottom-0.5 -right-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-emerald-500" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-sm sm:text-base font-bold text-slate-900">{clinicName}</h1>
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-bold text-emerald-700 border border-emerald-200">
                  متصل 24/7
                </span>
              </div>
              <p className="text-xs text-slate-400">حجز المواعيد والاستفسارات الفورية</p>
            </div>
          </div>

          <button
            onClick={handleNewSession}
            title="بدء محادثة جديدة"
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-bold text-slate-600 transition hover:bg-slate-100 hover:text-slate-900 shadow-sm"
          >
            <span>محادثة جديدة</span>
            <span className="text-sm">🔄</span>
          </button>
        </header>

        {/* ── مساحة الرسائل (Body) ── */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-slate-50/50">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center p-4">
              <div
                className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl text-2xl border shadow-sm"
                style={{ backgroundColor: `${brandColor}15`, color: brandColor, borderColor: `${brandColor}30` }}
              >
                ✨
              </div>
              <h2 className="text-lg sm:text-xl font-extrabold text-slate-900">{welcomeText}</h2>
              <p className="mt-1 max-w-sm text-xs sm:text-sm text-slate-500 leading-relaxed">
                يسعدني الرد على كافة استفساراتك الطبية ومساعدتك في حجز موعدك بسهولة.
              </p>

              <div className="mt-6 flex flex-wrap items-center justify-center gap-2 max-w-md">
                <button
                  onClick={() => handleSendMessage('عايز احجز موعد')}
                  className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
                >
                  📅 حجز موعد
                </button>
                <button
                  onClick={() => handleSendMessage('اسعار الكشف والخدمات كام؟')}
                  className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
                >
                  💰 الأسعار والخدمات
                </button>
                <button
                  onClick={() => handleSendMessage('ايه العروض اللي عندكم حالياً؟')}
                  className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
                >
                  🎁 العروض والخصومات
                </button>
                <button
                  onClick={() => handleSendMessage('مكان وعنوان العيادة فين؟')}
                  className="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-bold text-slate-700 shadow-sm transition hover:bg-slate-50"
                >
                  📍 العنوان واللوكيشن
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={msg.id}
                  className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1`}
                >
                  <div
                    className={`flex items-end gap-2 max-w-[85%] sm:max-w-[78%] ${
                      isUser ? 'flex-row-reverse' : 'flex-row'
                    }`}
                  >
                    <div
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm shadow-sm ${
                        isUser ? 'bg-slate-200 text-slate-700' : 'text-white'
                      }`}
                      style={!isUser ? { backgroundColor: brandColor } : {}}
                    >
                      {isUser ? '👤' : '🦷'}
                    </div>
                    <div
                      className={`rounded-2xl p-3.5 sm:p-4 text-xs sm:text-sm leading-relaxed whitespace-pre-wrap ${
                        isUser
                          ? 'text-white rounded-tl-none font-medium shadow-md'
                          : 'bg-white border border-slate-200/90 text-slate-800 rounded-tr-none shadow-sm'
                      }`}
                      style={isUser ? { backgroundColor: brandColor } : {}}
                    >
                      {renderFormattedText(msg.content)}
                    </div>
                  </div>
                  <span className="px-10 text-[10px] text-slate-400 font-mono">{msg.time}</span>
                </div>
              );
            })
          )}

          {isLoading && (
            <div className="flex items-center gap-2">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-xl text-white text-sm"
                style={{ backgroundColor: brandColor }}
              >
                🦷
              </div>
              <div className="flex items-center gap-1.5 rounded-2xl rounded-tr-none border border-slate-200 bg-white px-4 py-2.5 text-xs text-slate-400 shadow-sm">
                <span>جاري الرد</span>
                <div className="flex gap-1">
                  <span className="h-1.5 w-1.5 rounded-full animate-bounce" style={{ backgroundColor: brandColor }} />
                  <span className="h-1.5 w-1.5 rounded-full animate-bounce [animation-delay:0.2s]" style={{ backgroundColor: brandColor }} />
                  <span className="h-1.5 w-1.5 rounded-full animate-bounce [animation-delay:0.4s]" style={{ backgroundColor: brandColor }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* ── حقل الإدخال (Input Footer) ── */}
        <footer className="border-t border-slate-100 bg-white p-3 sm:p-4 shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="relative flex items-center gap-2"
          >
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="اكتب استفسارك هنا (مثال: احجز موعد، أو اسأل عن الأسعار)..."
              className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 pl-12 text-xs sm:text-sm text-slate-800 placeholder-slate-400 outline-none transition focus:bg-white focus:ring-2"
              style={{ caretColor: brandColor }}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute left-1.5 flex h-9 w-9 items-center justify-center rounded-xl text-white shadow-md transition disabled:opacity-40 shrink-0"
              style={{ backgroundColor: brandColor }}
            >
              <svg className="h-4 w-4 rotate-180 transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>
          <div className="mt-2 flex items-center justify-between px-1 text-[10px] text-slate-400">
            <span>⚡ نظام الاستقبال والمواعيد لـ {clinicName}</span>
            <span>اضغط Enter للإرسال</span>
          </div>
        </footer>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center bg-slate-100 font-sans">جاري التحميل...</div>}>
      <ChatComponent />
    </Suspense>
  );
}