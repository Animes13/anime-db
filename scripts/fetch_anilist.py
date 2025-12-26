# scripts/fetch_anilist.py
import requests
import json
import time

ANILIST_API = "https://graphql.anilist.co"

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

def fetch_all_anime():
    page = 1
    all_items = []

    while True:
        print(f"📡 AniList page {page}")
        r = requests.post(
            ANILIST_API,
            json={"query": QUERY, "variables": {"page": page}},
            timeout=20
        )
        r.raise_for_status()
        data = r.json()["data"]["Page"]

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
        time.sleep(0.6)

    return all_items

if __name__ == "__main__":
    items = fetch_all_anime()
    with open("data/anilist_raw.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"✅ Total animes: {len(items)}")
