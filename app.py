import os
import json
from flask import Flask, request, jsonify
from github import Github

app = Flask(__name__)

# Environment variables
TMDB_API_KEY = os.environ.get("d69381011732433769e410a89558dfde")
GITHUB_TOKEN = os.environ.get("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")
GITHUB_REPO = os.environ.get("ArchitSharma101/test-player-01")  # e.g., 'username/repo'
BRANCH = os.environ.get("GITHUB_BRANCH", "main")

# Movie template file path (local)
MOVIE_TEMPLATE_PATH = "movie_template.html"

# Movies JSON path (local)
MOVIES_JSON_PATH = "movies.json"

# Initialize GitHub client
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

@app.route("/add_movie", methods=["POST"])
def add_movie():
    data = request.json
    movie_name = data.get("name")

    if not movie_name:
        return jsonify({"error": "Movie name required"}), 400

    # Fetch TMDB movie data
    import requests
    search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_name}"
    search_resp = requests.get(search_url).json()
    results = search_resp.get("results")
    if not results:
        return jsonify({"error": "Movie not found in TMDB"}), 404

    movie = results[0]
    movie_id = movie["id"]
    title = movie.get("title", "")
    overview = movie.get("overview", "")
    release_date = movie.get("release_date", "")
    year = release_date.split("-")[0] if release_date else ""
    # For simplicity, director as "Unknown"
    director = "Unknown"

    # Read movie template
    with open(MOVIE_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # Replace placeholders
    html_content = template.replace("{{TITLE}}", title)\
                           .replace("{{DIRECTOR}}", director)\
                           .replace("{{YEAR}}", year)\
                           .replace("{{DESCRIPTION}}", overview)\
                           .replace("{{TMDB_ID}}", str(movie_id))

    # Path to push in repo
    movie_file_path = f"movies/{movie_id}.html"

    # Push movie page to GitHub
    try:
        repo.create_file(movie_file_path, f"Add movie {title}", html_content, branch=BRANCH)
    except:
        # If file exists, update
        contents = repo.get_contents(movie_file_path, ref=BRANCH)
        repo.update_file(contents.path, f"Update movie {title}", html_content, contents.sha, branch=BRANCH)

    # Update movies.json
    try:
        contents = repo.get_contents(MOVIES_JSON_PATH, ref=BRANCH)
        movies_list = json.loads(contents.decoded_content.decode())
    except:
        movies_list = []

    # Avoid duplicates
    if not any(m.get("id") == movie_id for m in movies_list):
        movies_list.append({
            "id": movie_id,
            "title": title,
            "genre": " / ".join([g.get("name", "") for g in movie.get("genres", [])]) if movie.get("genres") else "",
            "description": overview
        })

    updated_json = json.dumps(movies_list, indent=2)

    # Push updated JSON
    try:
        repo.update_file(contents.path, f"Update movies.json for {title}", updated_json, contents.sha, branch=BRANCH)
    except:
        repo.create_file(MOVIES_JSON_PATH, f"Create movies.json with {title}", updated_json, branch=BRANCH)

    return jsonify({"success": True, "movie_id": movie_id})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
