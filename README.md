<div align="center">

# 🎬 CineMatch

### Less scrolling. More “that looks good.”

Pick a movie you love. Find films with a similar vibe. Then wander through what’s trending, popular, and playing now.

**A local movie-discovery app powered by TMDB, SQLite, and text-based similarity.**

</div>

---

## 🍿 The idea

Choosing a movie can take longer than watching one. CineMatch gives you a starting point: choose a title, and it finds movies with similar descriptions and genres. When you want something different, browse TMDB’s current **Trending**, **Popular**, and **Now Playing** lists.

No mystery algorithm claiming to know your soul. Just movie data, text vectorization, and a useful shortlist.

## ✨ What it does

- **Similar Movies** — recommends titles from your local catalogue using TF-IDF vectors and cosine similarity.
- **Trending** — browse TMDB’s weekly trending films.
- **Popular** — see TMDB’s current popular movies.
- **Now Playing** — discover movies currently in theaters.
- **Daily catalogue refresh** — fetches selected TMDB lists, updates movie details, and rebuilds the recommendation model.
- **Local storage** — keeps the catalogue in SQLite and the generated model on your computer.

The three discovery lists are fetched from TMDB and cached for 30 minutes. The local catalogue and similarity model refresh when you run the updater or its scheduled task.

## 🧠 How recommendations work

1. The updater collects a bounded selection of trending, popular, and now-playing movies from TMDB.
2. Movie details are saved in `data/cinematch.sqlite3`, keyed by TMDB movie ID so repeat updates refresh existing rows.
3. CineMatch combines each title, overview, and genre text, then vectorizes it with TF-IDF.
4. Cosine similarity ranks the closest titles for the movie you selected.

The catalogue is intentionally manageable for a personal laptop. It is not a download of every movie in TMDB.

## 🚀 Run CineMatch locally

### 1. Install Python

Use Python 3.10 or newer.

### 2. Open this folder in VS Code

Open a PowerShell terminal in the CineMatch project folder—the folder containing `app.py` and `requirements.txt`.

### 3. Create the environment and install packages

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Activation is optional; calling the environment’s Python directly avoids PowerShell script-policy issues.

### 4. Add your TMDB credential

Copy `.env.example` to `.env`. In `.env`, fill in **one** credential:

```text
TMDB_API_KEY=your_v3_api_key
```

or

```text
TMDB_READ_ACCESS_TOKEN=your_api_read_access_token
```

Keep the real `.env` private. It is excluded by `.gitignore`; `.env.example` is safe to share because its values are blank.

### 5. Build the catalogue and recommendation model

```powershell
.\.venv\Scripts\python.exe update_movies.py
```

This creates `data/cinematch.sqlite3` and `data/movie_model.joblib`.

### 6. Start the app

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Streamlit prints a local address—open it in your browser. Keep the terminal open while you use CineMatch.

## ⏰ Make the catalogue update daily

On Windows, create a daily task in **Task Scheduler**:

- **Program:** the project’s `.venv\Scripts\python.exe`
- **Arguments:** the full path to `update_movies.py`
- **Start in:** the CineMatch project folder

The updater can run while the app is closed. Your laptop must be awake and online, and—if the task is set to run only while you are logged in—you must be signed in. Enable **Run task as soon as possible after a scheduled start is missed** to catch up after the laptop was unavailable.

After an update, refresh the browser page to load the newest catalogue and model.

## ☁️ Deploy a shareable version

You can deploy the public GitHub repository with [Streamlit Community Cloud](https://share.streamlit.io/):

1. Connect the GitHub account that owns this repository.
2. Create an app from the CineMatch repository, branch `main`, and entrypoint `app.py`.
3. In the app's **Advanced settings → Secrets**, add one credential in TOML format:

   ```toml
   TMDB_API_KEY = "your_v3_api_key"
   ```

   Or use `TMDB_READ_ACCESS_TOKEN` instead. Never paste a real credential into GitHub.
4. Deploy. On first launch, CineMatch builds its catalogue and model in the app environment; it does not need the local `data/` folder committed to GitHub.

The live Trending, Popular, and Now Playing tabs fetch TMDB data when the app reruns (cached for 30 minutes). Your Windows Task Scheduler updates your laptop's local catalogue only; it does not run inside the deployed app.

## 🗂️ Project files

```text
CineMatch/
├── app.py                 # Streamlit interface and recommendations
├── update_movies.py       # TMDB refresh and model-building job
├── requirements.txt       # Python packages
├── .env.example           # Blank credential template
├── .gitignore             # Keeps local secrets and generated files out of Git
└── data/                  # Created locally: SQLite catalogue and model
```

## 🔐 GitHub-safe by design

Share the source code, README, requirements, `.gitignore`, `.env.example`, and a screenshot of the app. Do **not** commit `.env`, `.venv`, or `data/`. Each person who clones the project creates their own `.env` and runs the updater to build their local catalogue and model.

## 🙏 Credits

Movie information and images are provided by [TMDB](https://www.themoviedb.org/).

> This product uses the TMDB API but is not endorsed or certified by TMDB.

