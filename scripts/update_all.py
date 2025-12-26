# scripts/update_all.py
import json
from datetime import datetime

with open("data/anilist_enriched.json", encoding="utf-8") as f:
    items = json.load(f)

tv = []
movies = []
index = {}

for a in items:
    entry = {
        "anilist_id": a["anilist_id"],
        "titles": a["titles"],
        "synonyms": a["synonyms"],
        "genres": a["genres"],
        "episodes": a["episodes"],
        "year": a["year"],
        "status": a["status"],
        "tmdb": a["tmdb"]
    }

    if a["format"] == "MOVIE":
        movies.append(entry)
        index[str(a["anilist_id"])] = "movie"
    else:
        tv.append(entry)
        index[str(a["anilist_id"])] = "tv"

with open("data/anime_tv.json", "w", encoding="utf-8") as f:
    json.dump(tv, f, ensure_ascii=False, indent=2)

with open("data/anime_movies.json", "w", encoding="utf-8") as f:
    json.dump(movies, f, ensure_ascii=False, indent=2)

with open("data/index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2)

meta = {
    "source": "AniList + TMDB",
    "last_update": datetime.utcnow().isoformat(),
    "tv_count": len(tv),
    "movie_count": len(movies)
}

with open("data/meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=2)

print("✅ Banco atualizado com sucesso")
