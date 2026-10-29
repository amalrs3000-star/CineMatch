from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import date
from pathlib import Path

import joblib
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from sklearn.feature_extraction.text import TfidfVectorizer
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "cinematch.sqlite3"
MODEL_PATH = DATA_DIR / "movie_model.joblib"
TMDB_API = "https://api.themoviedb.org/3"
PAGES = {"trending/movie/week": 2, "movie/popular": 5, "movie/now_playing": 3}
MAX_DETAIL_REQUESTS = 250
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4, connect=4, read=4, backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def get_api_credentials() -> tuple[str, str]:
    load_dotenv(ROOT / ".env")
    # TMDB provides a v3 API key and a separate API Read Access Token.
    # Prefer the Read Access Token when both are configured.
    access_token = os.getenv("TMDB_READ_ACCESS_TOKEN", "").strip()
    api_key = os.getenv("TMDB_API_KEY", "").strip()
    if access_token and access_token != "put_your_api_read_access_token_here":
        return access_token, "bearer"
    if api_key and api_key != "put_your_v3_api_key_here":
        return api_key, "api_key"
    raise RuntimeError(
        "Set TMDB_API_KEY (v3 key) or TMDB_READ_ACCESS_TOKEN "
        "(API Read Access Token) in the .env file."
    )


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            tmdb_id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            overview TEXT NOT NULL DEFAULT '',
            release_date TEXT NOT NULL DEFAULT '',
            vote_average REAL,
            vote_count INTEGER,
            popularity REAL,
            poster_path TEXT,
            genres TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title)")
    return db


def tmdb_get(
    session: requests.Session,
    credential: str,
    auth_type: str,
    endpoint: str,
    **params,
):
    headers = {"accept": "application/json"}
    request_params = {"language": "en-US", **params}
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {credential}"
    else:
        request_params["api_key"] = credential
    response = session.get(
        f"{TMDB_API}/{endpoint.lstrip('/')}",
        headers=headers,
        params=request_params,
        timeout=(5, 20),
    )
    response.raise_for_status()
    return response.json()


def collect_movie_ids(
    session: requests.Session, credential: str, auth_type: str
) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for endpoint, pages in PAGES.items():
        for page in range(1, pages + 1):
            payload = tmdb_get(session, credential, auth_type, endpoint, page=page)
            for item in payload.get("results", []):
                if item.get("id") and item.get("media_type", "movie") == "movie":
                    movie_id = int(item["id"])
                    if movie_id not in seen:
                        ids.append(movie_id)
                        seen.add(movie_id)
            logging.info("Collected page %s of %s", page, endpoint)
    return ids


def upsert_movie(db: sqlite3.Connection, movie: dict) -> None:
    db.execute("""
        INSERT INTO movies
        (tmdb_id, title, overview, release_date, vote_average, vote_count,
         popularity, poster_path, genres, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tmdb_id) DO UPDATE SET
          title=excluded.title, overview=excluded.overview,
          release_date=excluded.release_date, vote_average=excluded.vote_average,
          vote_count=excluded.vote_count, popularity=excluded.popularity,
          poster_path=excluded.poster_path, genres=excluded.genres,
          updated_at=excluded.updated_at
    """, (
        int(movie["id"]), movie.get("title") or movie.get("original_title") or "Untitled",
        movie.get("overview") or "", movie.get("release_date") or "",
        movie.get("vote_average"), movie.get("vote_count"), movie.get("popularity"),
        movie.get("poster_path"), ", ".join(movie.get("genres") or []), date.today().isoformat(),
    ))


def update_catalogue() -> None:
    credential, auth_type = get_api_credentials()
    session = make_session()
    ids = collect_movie_ids(session, credential, auth_type)[:MAX_DETAIL_REQUESTS]
    logging.info("Refreshing details for up to %s movies", len(ids))

    with connect() as db:
        for number, movie_id in enumerate(ids, start=1):
            try:
                details = tmdb_get(session, credential, auth_type, f"movie/{movie_id}")
                details["genres"] = [g.get("name", "") for g in details.get("genres", [])]
                upsert_movie(db, details)
            except requests.RequestException as exc:
                logging.warning("Skipping TMDB movie %s: %s", movie_id, exc)
            if number % 25 == 0:
                db.commit()
                logging.info("Processed %s of %s", number, len(ids))
            time.sleep(0.08)
        db.commit()

    build_model()
    logging.info("Daily catalogue refresh completed. Database: %s", DB_PATH)


def build_model() -> None:
    with connect() as db:
        rows = db.execute("""
            SELECT tmdb_id, title, overview, genres
            FROM movies
            WHERE TRIM(title) <> ''
            ORDER BY title COLLATE NOCASE
        """).fetchall()

    if len(rows) < 2:
        raise RuntimeError("At least two movies are needed before building recommendations.")

    movie_ids = [int(row["tmdb_id"]) for row in rows]
    documents = [
        " ".join([row["title"] or "", row["overview"] or "", row["genres"] or ""]).strip()
        for row in rows
    ]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=100_000, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(documents)
    artifact = {"movie_ids": movie_ids, "vectorizer": vectorizer, "matrix": matrix}
    temporary = MODEL_PATH.with_suffix(".tmp")
    joblib.dump(artifact, temporary)
    temporary.replace(MODEL_PATH)
    logging.info("Built TF-IDF recommendation model from %s movies.", len(movie_ids))


if __name__ == "__main__":
    update_catalogue()
