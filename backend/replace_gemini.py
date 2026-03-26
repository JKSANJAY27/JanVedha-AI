import os
import glob

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content.replace('"gemini-1.5-flash"', '"gemini-2.5-flash"')
        new_content = new_content.replace("'gemini-1.5-flash'", "'gemini-2.5-flash'")
        new_content = new_content.replace('"gemini-2.0-flash"', '"gemini-2.5-flash"')
        new_content = new_content.replace("'gemini-2.0-flash'", "'gemini-2.5-flash'")
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {filepath}")
    except Exception as e:
        print(f"Failed on {filepath}: {e}")

backend_dir = r"c:\Users\harsh\Documents\JanVedha\JanVedha-AI\backend\app"

for root, dirs, files in os.walk(backend_dir):
    for filename in files:
        if filename.endswith(".py"):
            replace_in_file(os.path.join(root, filename))

print("Done replacing.")
