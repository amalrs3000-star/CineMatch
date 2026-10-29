from __future__ import annotations

import sqlite3
import os
from pathlib import Path

import joblib
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "cinematch.sqlite3"
MODEL_PATH = ROOT / "data" / "movie_model.joblib"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_API = "https://api.themoviedb.org/3"
PLACEHOLDER = "https://placehold.co/500x750/171717/FFFFFF?text=Poster+Unavailable"

st.set_page_config(page_title="CineMatch", page_icon="🎬", layout="wide")
load_dotenv(ROOT / ".env")


@st.cache_resource
def load_artifact(model_updated_at):
    return joblib.load(MODEL_PATH)


@st.cache_data
def load_movies(database_updated_at):
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as db:
        return pd.read_sql_query(
            "SELECT tmdb_id, title, overview, release_date, vote_average, poster_path, genres "
            "FROM movies ORDER BY title COLLATE NOCASE", db
        )


def recommendations(movie_id: int, count: int) -> list[dict]:
    artifact = load_artifact(MODEL_PATH.stat().st_mtime_ns)
    ids = artifact["movie_ids"]
    try:
        index = ids.index(int(movie_id))
    except ValueError:
        return []
    from sklearn.metrics.pairwise import cosine_similarity
    scores = cosine_similarity(artifact["matrix"][index], artifact["matrix"]).ravel()
    ranked = scores.argsort()[::-1]
    result = []
    for candidate in ranked:
        if candidate == index:
            continue
        result.append({"tmdb_id": ids[candidate], "score": float(scores[candidate])})
        if len(result) >= count:
            break
    return result


def poster(path):
    return f"{IMAGE_BASE}/{path.lstrip('/')}" if path else PLACEHOLDER


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_live_movies(endpoint: str) -> list[dict]:
    """Fetch a live TMDB discovery list and cache it for 30 minutes."""
    access_token = os.getenv("TMDB_READ_ACCESS_TOKEN", "").strip()
    api_key = os.getenv("TMDB_API_KEY", "").strip()
    headers = {"accept": "application/json"}
    params = {"language": "en-US", "page": 1}

    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    elif api_key:
        params["api_key"] = api_key
    else:
        raise RuntimeError("Add TMDB_API_KEY or TMDB_READ_ACCESS_TOKEN to .env.")

    response = requests.get(
        f"{TMDB_API}/{endpoint}",
        headers=headers,
        params=params,
        timeout=(5, 20),
    )
    response.raise_for_status()
    return response.json().get("results", [])


def render_live_movies(endpoint: str) -> None:
    try:
        items = fetch_live_movies(endpoint)
    except (requests.RequestException, RuntimeError):
        st.info("Could not load this TMDB list. Check the credential in .env and try again.")
        return

    if not items:
        st.info("TMDB did not return any movies for this list.")
        return

    columns = st.columns(5)
    for index, item in enumerate(items[:20]):
        with columns[index % len(columns)]:
            title = item.get("title") or item.get("original_title") or "Untitled"
            st.image(
                poster(item.get("poster_path")),
                width="stretch",
                alt=f"Poster for {title}",
            )
            st.markdown(f"**{title}**")
            details = []
            rating = item.get("vote_average")
            if rating is not None:
                details.append(f"⭐ {float(rating):.1f}/10")
            release_date = item.get("release_date")
            if release_date:
                details.append(str(release_date)[:4])
            if details:
                st.caption(" · ".join(details))
            overview = item.get("overview")
            if overview:
                with st.expander("Overview"):
                    st.write(overview)


st.title("🎬 CineMatch")
st.caption("Discover movies and find similar titles from your refreshed catalogue.")
movies = load_movies(DB_PATH.stat().st_mtime_ns) if DB_PATH.exists() else load_movies(0)

if movies.empty or not MODEL_PATH.exists():
    st.info("The movie catalogue and recommendation model are not ready yet.")
    st.write("Set up your TMDB key, then run the daily update once to collect movies and build the first model.")
    st.code("python update_movies.py")
    st.stop()

recommend_tab, trending_tab, popular_tab, playing_tab = st.tabs(
    ["✨ Similar movies", "🔥 Trending", "⭐ Popular", "🎟️ Now playing"]
)

with recommend_tab:
    selected_label = st.selectbox(
        "Choose a movie you like",
        options=movies["tmdb_id"].tolist(),
        format_func=lambda movie_id: movies.loc[movies.tmdb_id == movie_id, "title"].iloc[0],
    )
    count = st.slider("Recommendations", min_value=3, max_value=10, value=5)

    if st.button("Find similar movies", type="primary"):
        st.session_state["picked_movie"] = int(selected_label)
        st.session_state["recs"] = recommendations(int(selected_label), count)

    if "recs" in st.session_state:
        chosen = movies[movies.tmdb_id == st.session_state["picked_movie"]].iloc[0]
        st.subheader(f"Because you chose {chosen['title']}")
        rec_ids = [r["tmdb_id"] for r in st.session_state["recs"]]
        rec_movies = movies[movies.tmdb_id.isin(rec_ids)].copy()
        score_by_id = {r["tmdb_id"]: r["score"] for r in st.session_state["recs"]}
        rec_movies["score"] = rec_movies.tmdb_id.map(score_by_id)
        rec_movies = rec_movies.sort_values("score", ascending=False)

        columns = st.columns(5)
        for pos, (_, movie) in enumerate(rec_movies.iterrows()):
            with columns[pos % len(columns)]:
                st.image(
                    poster(movie["poster_path"]),
                    width="stretch",
                    alt=f"Poster for {movie['title']}",
                )
                st.markdown(f"**{movie['title']}**")
                details = []
                if pd.notna(movie["vote_average"]):
                    details.append(f"⭐ {movie['vote_average']:.1f}/10")
                if movie["release_date"]:
                    details.append(str(movie["release_date"])[:4])
                if details:
                    st.caption(" · ".join(details))
                if movie["overview"]:
                    with st.expander("Overview"):
                        st.write(movie["overview"])

with trending_tab:
    st.subheader("Trending this week")
    render_live_movies("trending/movie/week")

with popular_tab:
    st.subheader("Popular movies")
    render_live_movies("movie/popular")

with playing_tab:
    st.subheader("Now playing")
    render_live_movies("movie/now_playing")

st.divider()
st.caption(
    "Recommendations use TF-IDF text vectors over movie titles, descriptions, and genres. "
    "TMDB data is refreshed by running update_movies.py."
)
st.caption("This product uses the TMDB API but is not endorsed or certified by TMDB.")
