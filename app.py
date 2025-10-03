import os
import json
import threading
from flask import Flask, request, jsonify, send_from_directory
from github import Github, GithubException
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

# Environment variables
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "d69381011732433769e410a89558dfde")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "ArchitSharma101/test-player-01")
BRANCH = "main"

if not GITHUB_TOKEN:
    raise RuntimeError("GITHUB_TOKEN environment variable is required!")

# Initialize GitHub client
try:
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)
except GithubException as e:
    raise RuntimeError(f"Failed to access GitHub repo: {e}")

# Paths
MOVIE_TEMPLATE_PATH = "movie_template.html"
LOCAL_MOVIES_JSON = os.path.join(app.static_folder, "movies.json")
LOCAL_MOVIES_FOLDER = os.path.join(app.static_folder, "movies")

os.makedirs(LOCAL_MOVIES_FOLDER, exist_ok=True)

# Serve favicon safely
@app.route("/favicon.ico")
def favicon():
    path = os.path.join(app.root_path, 'static', 'favicon.ico')
    if os.path.exists(path):
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')
    return "", 204

# Health check
@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Server is running"}), 200

def push_to_github(file_path, repo_path, commit_message):
    """Push a local file to GitHub (non-blocking)"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        try:
            gh_file = repo.get_contents(repo_path, ref=BRANCH)
            repo.update_file(gh_file.path, commit_message, content, gh_file.sha, branch=BRANCH)
        except GithubException:
            repo.create_file(repo_path, commit_message, content, branch=BRANCH)
    except GithubException as e:
        print(f"GitHub push failed for {repo_path}: {e}")

@app.route("/add_movie", methods=["POST"])
def add_movie():
    data = request.json
    movie_name = data.get("name")

    if not movie_name:
        return jsonify({"error": "Movie name required"}), 400

    import requests
    try:
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_name}"
        resp = requests.get(search_url, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results")
        if not results:
            return jsonify({"error": "Movie not found in TMDB"}), 404
    except requests.RequestException as e:
        return jsonify({"error": f"TMDB API request failed: {str(e)}"}), 500

    movie = results[0]
    title = movie.get("title", "")
    overview = movie.get("overview", "")
    release_date = movie.get("release_date", "")
    year = release_date.split("-")[0] if release_date else ""
    director = "Unknown"

    # Generate safe filename: remove spaces, lowercase
    safe_title = "".join(c for c in title if c.isalnum()).lower()
    movie_file_name = f"{safe_title}.html"
    movie_file_path = os.path.join(LOCAL_MOVIES_FOLDER, movie_file_name)

    # Read template
    try:
        with open(MOVIE_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        return jsonify({"error": f"{MOVIE_TEMPLATE_PATH} not found"}), 500

    html_content = template.replace("{{ title }}", title)\
                           .replace("{{ director }}", director)\
                           .replace("{{ year }}", year)\
                           .replace("{{ description }}", overview)\
                           .replace("{{ tmdb_id }}", str(movie.get("id", "")))

    # Save movie HTML locally
    with open(movie_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Update local movies.json
    if os.path.exists(LOCAL_MOVIES_JSON):
        with open(LOCAL_MOVIES_JSON, "r", encoding="utf-8") as f:
            movies_list = json.load(f)
    else:
        movies_list = []

    if not any(m.get("title").lower() == title.lower() for m in movies_list):
        movies_list.append({
            "id": movie.get("id"),
            "title": title,
            "genre": " / ".join([g.get("name", "") for g in movie.get("genres", [])]) if movie.get("genres") else "",
            "description": overview,
            "file": f"movies/{movie_file_name}"
        })

    with open(LOCAL_MOVIES_JSON, "w", encoding="utf-8") as f:
        json.dump(movies_list, f, indent=2)

    # Push to GitHub in a separate thread (non-blocking)
    threading.Thread(target=push_to_github, args=(movie_file_path, f"movies/{movie_file_name}", f"Add movie {title}")).start()
    threading.Thread(target=push_to_github, args=(LOCAL_MOVIES_JSON, "movies.json", f"Update movies.json with {title}")).start()

    return jsonify({"success": True, "file": movie_file_name, "title": title})
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
