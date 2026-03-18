"""
Quick test: does the NewsAPI key work? Runs directly.
Usage: python scripts/test_newsapi.py
"""
import urllib.request
import urllib.parse
import json

API_KEY = "2082e154a8944e1988b2c6015c6b7ddc"
BASE = "https://newsapi.org/v2/everything"

tests = [
    ("India civic simple", "India+civic+municipal"),
    ("India pothole", "India+pothole"),
    ("India garbage", "India+garbage+municipal"),
    ("Chennai civic", "Chennai+civic"),
]

for name, q in tests:
    url = f"{BASE}?q={q}&language=en&sortBy=publishedAt&pageSize=5&apiKey={API_KEY}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            count = data.get("totalResults", 0)
            status = data.get("status", "?")
            articles = data.get("articles", [])
            print(f"\n[{name}] status={status} total={count}")
            for a in articles[:3]:
                print(f"  - {a.get('title', '')[:80]}")
                print(f"    URL: {a.get('url', '')[:80]}")
    except Exception as e:
        print(f"\n[{name}] ERROR: {e}")
