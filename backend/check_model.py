import sys
sys.path.insert(0, '.')
import google.generativeai as genai
from app.core.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
flash_models = [m for m in models if 'flash' in m.lower()]
print("Flash models available:")
for m in flash_models:
    print(" ", m)

# Try the specific model name used
MODEL_NAME = "gemini-2.5-flash"
try:
    model = genai.GenerativeModel(MODEL_NAME)
    r = model.generate_content("Say: OK")
    print(f"\n✅ Model '{MODEL_NAME}' works. Response: {r.text[:50]}")
except Exception as e:
    print(f"\n❌ Model '{MODEL_NAME}' failed: {type(e).__name__}: {e}")
    # Try the preview variant
    for candidate in flash_models:
        try:
            name_short = candidate.replace("models/", "")
            model2 = genai.GenerativeModel(name_short)
            r2 = model2.generate_content("Say: OK")
            print(f"✅ '{name_short}' works: {r2.text[:40]}")
            break
        except Exception as e2:
            print(f"  ❌ '{name_short}' also failed: {e2}")
