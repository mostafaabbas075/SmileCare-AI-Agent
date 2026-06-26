from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, BaseMessage
import structlog

from app.core.config import settings
from app.rag.sentence_embedder import SentenceTransformerEmbedder
from app.rag.qdrant_retriever import ClinicRetriever

logger = structlog.get_logger(__name__)

# 🧠 قاموس (Dictionary) لتخزين ذاكرة المحادثة في الرامات لكل مريض (Session)
chat_memory_store: Dict[str, List[BaseMessage]] = {}

# --- 1. تعريف أداة الحجز (الأكشن) ---
def book_dental_appointment(patient_name: str, patient_age: int, phone_number: str, date: str, time: str) -> str:
    """
    يقوم بحجز موعد أسنان للمريض في العيادة.
    يجب أن لا تستخدم هذه الأداة أبدًا إلا إذا أعطاك المريض هذه المعلومات الثلاثة صراحة: الاسم، السن، ورقم الهاتف.
    
    Args:
        patient_name: اسم المريض
        patient_age: سن المريض
        phone_number: رقم هاتف المريض
        date: اليوم المطلوب للحجز (مثل: غدا، السبت)
        time: الوقت المطلوب للحجز (مثل: 5 مساء)
    """
    if "جمعة" in date or "friday" in date.lower():
        return "العيادة مغلقة يوم الجمعة. أخبر المريض أن يختار يوماً آخر."
        
    return f"نجاح: تم حجز الموعد باسم {patient_name} (السن: {patient_age}) برقم هاتف {phone_number} ليوم {date} الساعة {time}. رقم التأكيد: #SMILE-7788"


class DentalAgent:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.1, 
            google_api_key=settings.GOOGLE_API_KEY
        )
        
        self.llm_with_tools = self.llm.bind_tools([book_dental_appointment])
        
        self.embedder = SentenceTransformerEmbedder()
        self.retriever = ClinicRetriever(embedder=self.embedder)

    async def run(self, message: str, session_id: str) -> str:
        """تنفيذ دورة المحادثة الكاملة للـ Agent مع الذاكرة"""
        
        # 1. استرجاع أو إنشاء ذاكرة جديدة لهذا الـ Session
        if session_id not in chat_memory_store:
            chat_memory_store[session_id] = []
            print(f"\n🆕 [New Session] مسار جديد بدأ للـ ID: {session_id}")
        else:
            print(f"\n🧠 [Memory Active] استرجاع الذاكرة للـ ID: {session_id} (عدد الرسائل المحفوظة: {len(chat_memory_store[session_id])})")
            
        history = chat_memory_store[session_id]
        
        # 2. استخراج السياق من ملفات العيادة
        context = await self.retriever.search(message)
        
        # 3. بناء الـ Prompt
        system_prompt = """أنت موظف استقبال افتراضي ذكي (AI Agent) تعمل في عيادة أسنان راقية.
        مهمتك الأساسية هي مساعدة المرضى والرد على استفساراتهم بناءً على معلومات العيادة.

        التعليمات الأساسية:
        1. الاعتماد على السياق: أجب فقط بناءً على "معلومات العيادة" المذكورة أدناه.
        2. قاعدة الحجز الصارمة: إذا طلب المريض حجز موعد، يجب عليك أولاً جمع 3 معلومات أساسية منه: (الاسم، السن، رقم الموبايل) بالإضافة إلى الموعد والوقت.
        لا تخمن أبداً أي معلومات، وإذا كان هناك أي معلومة ناقصة، اطلبها من المريض بلطف واحترافية.
        بمجرد اكتمال جميع البيانات، استخدم أداة الحجز المتاحة لك لتأكيد الموعد.
        3. يمنع التشخيص: أنت لست طبيباً. لا تقم بوصف أدوية أو تشخيص حالات.

        معلومات العيادة المستخرجة:
        {context}
        """
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"), # 🧠 هنا يتم تمرير الذاكرة السابقة
            ("human", "{user_message}")
        ])
        
        try:
            logger.info("generating_ai_response", session=session_id)
            
            # 4. دمج الرسائل الحالية مع الذاكرة
            messages = prompt_template.format_messages(
                context=context if context else "لا توجد معلومات إضافية.",
                chat_history=history,
                user_message=message
            )
            
            # 5. إرسال الطلب لـ Gemini
            response = await self.llm_with_tools.ainvoke(messages)
            
            # --- 6. دورة الـ Agent ومعالجة الرد (Guard) ---
            if response.tool_calls:
                print("⚙️ [Agent Action] Gemini لاحظ اكتمال البيانات وقرر ينفذ الحجز!")
                tool_call = response.tool_calls[0]
                
                if tool_call["name"] == "book_dental_appointment":
                    args = tool_call["args"]
                    print(f"📥 البيانات اللي جيميناي جمعها: {args}")
                    
                    tool_result = book_dental_appointment(**args)
                    print(f"✅ نتيجة الدالة: {tool_result}")
                    
                    messages.append(response) 
                    messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))
                    
                    final_response = await self.llm_with_tools.ainvoke(messages)
                    raw_content = final_response.content
                else:
                    raw_content = response.content
            else:
                raw_content = response.content
                
            # 🛡️ الحماية الصارمة (Guard) لمنع إيرور 422:
            # نجبر أي نوع داتا يرجع من LangChain إنه يتحول لنص نقي
            if isinstance(raw_content, list):
                text_parts = []
                for part in raw_content:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                final_text_to_return = " ".join(text_parts)
            elif not raw_content:
                final_text_to_return = "تم تنفيذ طلبك بنجاح."
            else:
                final_text_to_return = str(raw_content)
                
            final_text_to_return = final_text_to_return.strip()
            # ----------------------------------------------------
                
            # 🧠 7. حفظ المحادثة الحالية في الذاكرة للمرات القادمة
            history.append(HumanMessage(content=message))
            history.append(AIMessage(content=final_text_to_return))
            
            # الاحتفاظ بآخر 10 رسائل فقط
            if len(history) > 10:
                history = history[-10:]
                chat_memory_store[session_id] = history
                
            return final_text_to_return
            
        except Exception as e:
            logger.error("agent_execution_failed", error=str(e), session=session_id)
            return "عذراً، أواجه مشكلة تقنية في نظام العيادة حالياً. هل يمكنك إعادة إرسال رسالتك؟"