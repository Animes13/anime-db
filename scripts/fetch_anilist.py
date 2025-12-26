# scripts/fetch_anilist.py
import os
import requests
import json
import time

ANILIST_API = "https://graphql.anilist.co"
OUTPUT_FILE = "data/anilist_raw.json"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "anime-db-github-action"
}

# 🔒 Trava para evitar execução duplicada no GitHub Actions
if os.path.exists(OUTPUT_FILE):
    print("⚠️ anilist_raw.json já existe. Fetch ignorado.")
    exit(0)

QUERY = """
query ($page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo {
      hasNextPage
    }
    media(type: ANIME) {
      id
      format
      status
      episodes
      startDate { year }
      genres
      synonyms
      title {
        romaji
        english
        native
      }
    }
  }
}
"""

def safe_request(payload, retries=6):
    for attempt in range(retries):
        r = requests.post(
            ANILIST_API,
            headers=HEADERS,
            json=payload,
            timeout=30
        )

        if r.status_code == 200:
            return r.json()

        if r.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"⏳ Rate limit (429). Aguardando {wait}s...")
            time.sleep(wait)
            continue

        r.raise_for_status()

    raise RuntimeError("❌ AniList rate limit persistente")

def fetch_all_anime():
    page = 1
    all_items = []

    while True:
        print(f"📡 AniList page {page}")

        response = safe_request({
            "query": QUERY,
            "variables": {"page": page}
        })

        page_data = response["data"]["Page"]

        for m in page_data["media"]:
            all_items.append({
                "anilist_id": m["id"],
                "format": m["format"],
                "status": m["status"],
                "episodes": m["episodes"],
                "year": m["startDate"]["year"],
                "genres": m["genres"],
                "titles": m["title"],
                "synonyms": m["synonyms"],
                "tmdb": {}
            })

        if not page_data["pageInfo"]["hasNextPage"]:
            break

        page += 1
        time.sleep(0.6)  # 🔥 delay estável para GitHub Actions

    return all_items

if __name__ == "__main__":
    items = fetch_all_anime()

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"✅ Total de animes coletados: {len(items)}")
