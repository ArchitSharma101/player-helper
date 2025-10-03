import os
import json
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
MOVIES_JSON_PATH = "movies.json"

# Serve favicon safely
@app.route("/favicon.ico")
def favicon():
    path = os.path.join(app.root_path, 'static', 'favicon.ico')
    if os.path.exists(path):
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')
    return "", 204  # Return empty response if no favicon

# Root endpoint for health check
@app.route("/")
def home():
    return jsonify({"status": "ok", "message": "Server is running"}), 200

# Add movie endpoint
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
    movie_id = movie.get("id")
    title = movie.get("title", "")
    overview = movie.get("overview", "")
    release_date = movie.get("release_date", "")
    year = release_date.split("-")[0] if release_date else ""
    director = "Unknown"

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
                       .replace("{{ tmdb_id }}", str(movie_id))

    movie_file_path = f"movies/{movie_id}.html"

    # Push/update movie page
    try:
        try:
            contents = repo.get_contents(movie_file_path, ref=BRANCH)
            repo.update_file(contents.path, f"Update movie {title}", html_content, contents.sha, branch=BRANCH)
        except GithubException:
            repo.create_file(movie_file_path, f"Add movie {title}", html_content, branch=BRANCH)
    except GithubException as e:
        return jsonify({"error": f"GitHub update failed: {str(e)}"}), 500

    # Update movies.json
    try:
        contents = repo.get_contents(MOVIES_JSON_PATH, ref=BRANCH)
        movies_list = json.loads(contents.decoded_content.decode())
    except GithubException:
        movies_list = []

    if not any(m.get("id") == movie_id for m in movies_list):
        movies_list.append({
            "id": movie_id,
            "title": title,
            "genre": " / ".join([g.get("name", "") for g in movie.get("genres", [])]) if movie.get("genres") else "",
            "description": overview
        })

    updated_json = json.dumps(movies_list, indent=2)

    try:
        try:
            repo.update_file(contents.path, f"Update movies.json for {title}", updated_json, contents.sha, branch=BRANCH)
        except GithubException:
            repo.create_file(MOVIES_JSON_PATH, f"Create movies.json with {title}", updated_json, branch=BRANCH)
    except GithubException as e:
        return jsonify({"error": f"GitHub JSON update failed: {str(e)}"}), 500

    return jsonify({"success": True, "movie_id": movie_id})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # For Render/Gunicorn, use 0.0.0.0 as host
    app.run(host="0.0.0.0", port=port)


