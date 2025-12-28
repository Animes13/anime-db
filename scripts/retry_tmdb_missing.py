# -*- coding: utf-8 -*-

import json
import requests
import os
from concurrent.futures import ThreadPoolExecutor

TMDB_API = "https://api.themoviedb.org/3"
TOKEN = os.getenv("TMDB_TOKEN_1")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json;charset=utf-8"
}

REQUIRED = ["overview", "poster", "backdrop", "vote_average", "release_date"]

def tmdb_incompleto(tmdb):
    if not tmdb.get("id"):
        return True
    return any(not tmdb.get(k) for k in REQUIRED)

def search(query):
    r = requests.get(
        f"{TMDB_API}/search/multi",
        headers=HEADERS,
        params={"query": query},
        timeout=10
    )
    return r.json().get("results", []) if r.status_code == 200 else []

def fetch(media, tmdb_id):
    r = requests.get(
        f"{TMDB_API}/{media}/{tmdb_id}",
        headers=HEADERS,
        timeout=10
    )
    return r.json() if r.status_code == 200 else {}

def retry(item):
    tmdb = item["tmdb"]

    if not tmdb_incompleto(tmdb):
        return item

    titles = [
        item.get("titles", {}).get("romaji"),
        item.get("titles", {}).get("english"),
        item.get("titles", {}).get("native"),
    ]

    for title in filter(None, titles):
        for r in search(title):
            if r.get("media_type") not in ("tv", "movie"):
                continue

            d = fetch(r["media_type"], r["id"])
            tmdb.update({
                "id": r["id"],
                "media_type": r["media_type"],
                "poster": d.get("poster_path"),
                "backdrop": d.get("backdrop_path"),
                "overview": d.get("overview"),
                "vote_average": d.get("vote_average"),
                "release_date": d.get("first_air_date") or d.get("release_date"),
                "checked": True,
                "reason": "retry_success"
            })
            return item

    tmdb["reason"] = "retry_failed"
    return item

if __name__ == "__main__":
    with open("data/anilist_enriched.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    missing = [i for i in data if tmdb_incompleto(i["tmdb"])]
    print(f"🔁 Segunda chance para {len(missing)} itens")

    with ThreadPoolExecutor(4) as ex:
        ex.map(retry, missing)

    with open("data/anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("✅ Segunda chance concluída")