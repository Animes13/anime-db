# -*- coding: utf-8 -*-

import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor

TMDB_API = "https://api.themoviedb.org/3"
TOKEN = "SEU_TOKEN_AQUI"

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
    if item["tmdb"]["id"]:
        return item

    for title in [
        item.get("titles", {}).get("romaji"),
        item.get("titles", {}).get("native")
    ]:
        if not title:
            continue

        for r in search(title):
            if r.get("media_type") in ("tv", "movie"):
                item["tmdb"]["id"] = r["id"]
                item["tmdb"]["media_type"] = r["media_type"]
                item["tmdb"]["reason"] = "retry_success"
                return item

    return item

if __name__ == "__main__":
    with open("anilist_enriched.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    missing = [i for i in data if not i["tmdb"]["id"]]
    print(f"🔁 Segunda chance para {len(missing)} itens")

    with ThreadPoolExecutor(4) as ex:
        missing = list(ex.map(retry, missing))

    with open("anilist_enriched_retry.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("✅ Segunda tentativa concluída")
