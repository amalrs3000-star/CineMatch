# CineMatch — fresh local version

This is a separate app. It does not use or overwrite the old movie_list.pkl or similarity.pkl.

## First setup

1. Install Python 3.10 or newer.
2. Open this folder in VS Code.
3. In the terminal, run: python -m venv .venv
4. Activate it in PowerShell with: .\.venv\Scripts\Activate.ps1
5. Install packages with: python -m pip install -r requirements.txt
6. Create .env beside app.py. Set either TMDB_API_KEY to your v3 API key, or TMDB_READ_ACCESS_TOKEN to your API Read Access Token. The Read Access Token takes priority if both are set.
7. Run python update_movies.py once. This creates data/cinematch.sqlite3 and builds data/movie_model.joblib.
8. Start the app with: python -m streamlit run app.py

The updater fetches a bounded selection from TMDB weekly trending, popular, and now-playing lists; refreshes each selected movie's details; saves them in SQLite by TMDB ID; and rebuilds a TF-IDF similarity model from the current local catalogue. Running it again updates existing IDs rather than creating duplicate rows.

## Daily automation on Windows

Create a daily Windows Task Scheduler task:

- Program: the Python executable inside this folder's .venv\Scripts\python.exe
- Arguments: the full path to update_movies.py
- Start in: this CineMatch folder

The laptop needs to be on, awake, and online. The updater needs its .env file in this folder. The app can continue using the latest saved catalogue/model if it is closed during the update.

MAX_DETAIL_REQUESTS and the page counts in update_movies.py limit the size and API workload. This intentionally builds a useful current catalogue; it does not download every movie ever listed by TMDB.

TMDB supports a v3 API key or an API Read Access Token. Keep .env private; it is excluded by .gitignore.
