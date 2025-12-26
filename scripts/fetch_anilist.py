# scripts/fetch_anilist.py
import requests
import json
import time

ANILIST_API = "https://graphql.anilist.co"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "anime-db-github-action"
}

QUERY = """
query ($page: Int) {
  Page(page: $page, perPage: 25) {
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

def safe_request(payload, retries=5):
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
            wait = (attempt + 1) * 10
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

        data = safe_request({
            "query": QUERY,
            "variables": {"page": page}
        })["data"]["Page"]

        for m in data["media"]:
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

        if not data["pageInfo"]["hasNextPage"]:
            break

        page += 1
        time.sleep(1.2)  # 🔥 delay seguro para GitHub Actions

    return all_items

if __name__ == "__main__":
    items = fetch_all_anime()

    with open("data/anilist_raw.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"✅ Total de animes coletados: {len(items)}")
