import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.ai.classifier_agent import classify_complaint

# (lang, input_text, expected_dept_name)
TEST_CASES = [
    # ── English ──────────────────────────────────────────────────────────────
    ("en",    "Pothole is very huge near Gandhi Road, please fix it",           "Roads & Bridges"),
    ("en",    "Garbage dump at the corner of my street is stinking for 5 days", "Solid Waste Management"),
    ("en",    "There is no electricity since yesterday in Anna Nagar",           "Street Lighting"),
    ("en",    "Water pipe broken in MG road, water is leaking continuously",     "Water Supply"),
    ("en",    "Building without permission being constructed in my area",        "Buildings & Planning"),
    ("en",    "A tree has fallen over the park gate and blocking exit",          "Parks & Greenery"),
    ("en",    "Mosquitoes and dengue cases increasing in our locality",          "Health & Sanitation"),
    # ── Hinglish (romanised) ──────────────────────────────────────────────────
    ("hi-en", "Street light nahi chal raha hai kal se",                         "Street Lighting"),
    ("hi-en", "Kachra pada hai yahan, koi utha nahi raha",                      "Solid Waste Management"),
    ("hi-en", "Road pe bahut bada gaddha hai, accident ho sakta hai",           "Roads & Bridges"),
    ("hi-en", "Bahut macchar ho gaye hain idhar dengue ka darr hai",            "Health & Sanitation"),
    ("hi-en", "Pani nahi aa raha hai pipe mein",                                "Water Supply"),
    # ── Hindi (Devanagari script) ─────────────────────────────────────────────
    ("hi",    "सड़क पर बहुत बड़ा गड्ढा है, दुर्घटना हो सकती है",                "Roads & Bridges"),
    ("hi",    "कचरा पड़ा है यहाँ, कोई उठा नहीं रहा",                            "Solid Waste Management"),
    ("hi",    "बिजली नहीं है कल से इस इलाके में",                                "Street Lighting"),
    # ── Tamil (தமிழ் script) ──────────────────────────────────────────────────
    ("ta",    "பாதையில் பெரிய குழி உள்ளது, விபத்து ஆகலாம்",                   "Roads & Bridges"),
    ("ta",    "குப்பை கொட்டப்படுகிறது, துர்நாற்றம் வருகிறது",                  "Solid Waste Management"),
    ("ta",    "தெரு விளக்கு எரியவில்லை",                                       "Street Lighting"),
    # ── Bengali (বাংলা script) ────────────────────────────────────────────────
    ("bn",    "রাস্তায় বড় গর্ত আছে, দুর্ঘটনা হতে পারে",                      "Roads & Bridges"),
    ("bn",    "বৈদ্যুতিক সরবরাহ নেই এলাকায়",                                  "Street Lighting"),
    ("bn",    "বাগানে গাছ পড়েছে",                                              "Parks & Greenery"),
    # ── Marathi (मराठी script) ────────────────────────────────────────────────
    ("mr",    "रस्त्यावर मोठा खड्डा आहे, अपघात होऊ शकतो",                     "Roads & Bridges"),
    ("mr",    "विजेची कापड नाही",                                               "Street Lighting"),
    ("mr",    "उद्यानात झाड पडले",                                              "Parks & Greenery"),
]

def format_result(res) -> str:
    src = res.classifier_source.upper()
    return f"[{src}] {res.dept_name} (Conf: {res.confidence:.2f})"

async def async_main():
    header = f"{'LANG':<6} {'INPUT':<55} {'RESULT':<45} {'EXPECTED':<30} OK?"
    print(header)
    print("─" * len(header))

    correct = 0
    for lang, text, expected in TEST_CASES:
        res     = await classify_complaint(text)
        result  = format_result(res)
        hit     = "✅" if expected in res.dept_name else "❌"
        if expected in res.dept_name:
            correct += 1
        print(f"{lang:<6} {text[:52]:<55} {result:<45} {expected:<30} {hit}")

    total = len(TEST_CASES)
    print(f"\n{'─'*len(header)}")
    print(f"Score: {correct}/{total} ({100*correct//total}%)")

if __name__ == "__main__":
    asyncio.run(async_main())
