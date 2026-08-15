import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.GOOGLE_API_KEY)

print("🔍 جاري فحص النماذج المتاحة لمفتاحك...\n")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        name = m.name.replace('models/', '')
        try:
            model = genai.GenerativeModel(name)
            res = model.generate_content("hi")
            print(f"✅ شغال ومتاح: {name}")
        except Exception as e:
            print(f"❌ غير متاح ({type(e).__name__}): {name}")
