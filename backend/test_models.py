import google.generativeai as genai

with open('.env', 'r') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY='):
            api_key = line.strip().split('=', 1)[1]
            break

genai.configure(api_key=api_key)

with open('models.txt', 'w') as f:
    f.write("Available models:\n")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            f.write(m.name + '\n')
