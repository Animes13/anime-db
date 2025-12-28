# -*- coding: utf-8 -*-

import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor

TMDB_API = "https://api.themoviedb.org/3"
TOKEN = (
    __import__("os").getenv("TMDB_TOKEN_1")
    or __import__("os").getenv("TMDB_TOKEN_2")
)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json;charset=utf-8"
}

def search(query):
    r = requests.get(
        f"{TMDB_API}/search/multi",
        headers=HEADERS,
        params={"query": query},
        timeout=10
    )
    return r.json().get("results", []) if r.status_code == 200 else []

def retry(item):
    tmdb = item.get("tmdb", {})

    if tmdb.get("id") and tmdb.get("overview"):
        return item

    titles = [
        item.get("titles", {}).get("romaji"),
        item.get("titles", {}).get("native"),
    ]

    for title in filter(None, titles):
        for r in search(title):
            if r.get("media_type") in ("tv", "movie"):
                tmdb.update({
                    "id": r["id"],
                    "media_type": r["media_type"],
                    "checked": True,
                    "reason": "retry_success"
                })
                return item

    tmdb["reason"] = "not_found_final"
    tmdb["checked"] = True
    return item

if __name__ == "__main__":
    INPUT = "data/anilist_enriched.json"
    OUTPUT = "data/anilist_enriched.json"

    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    missing = [
        i for i in data
        if not i.get("tmdb", {}).get("id")
        or not i.get("tmdb", {}).get("overview")
    ]

    print(f"🔁 Segunda chance para {len(missing)} itens")

    with ThreadPoolExecutor(4) as ex:
        list(ex.map(retry, missing))

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("✅ Segunda tentativa concluída")