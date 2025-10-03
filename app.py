from flask import Flask, request, render_template
import requests, json, os
from jinja2 import Template
from github import Github

# CONFIG
TMDB_API_KEY = "YOUR_TMDB_API_KEY"
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN"
GITHUB_REPO = "username/repo-name"  # e.g., waterbears/movie-hub
BRANCH = "main"  # GitHub branch

app = Flask(__name__)

# Load movies
MOVIES_FILE = "movies.json"
if os.path.exists(MOVIES_FILE):
    with open(MOVIES_FILE) as f:
        movies = json.load(f)
else:
    movies = []

# Homepage route
@app.route("/")
def home():
    return render_template("index_template.html", movies=movies)

# Add movie form route
@app.route("/add-movie", methods=["GET", "POST"])
def add_movie():
    global movies
    if request.method == "POST":
        movie_name = request.form["movie_name"]
        # Fetch movie from TMDB
        tmdb_data = fetch_movie_from_tmdb(movie_name)
        if tmdb_data:
            # Generate movie page
            create_movie_page(tmdb_data)
            # Update homepage
            movies.append(tmdb_data)
            update_homepage()
            # Save locally
            with open(MOVIES_FILE, "w") as f:
                json.dump(movies, f, indent=2)
            # Push to GitHub
            push_to_github(tmdb_data)
            return f"Movie '{movie_name}' added successfully!"
        else:
            return f"Movie '{movie_name}' not found."
    return '''
        <form method="POST">
            Movie Name: <input name="movie_name">
            <button type="submit">Add Movie</button>
        </form>
    '''

# Fetch TMDB
def fetch_movie_from_tmdb(name):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={name}"
    r = requests.get(url).json()
    results = r.get("results")
    if not results:
        return None
    movie = results[0]
    return {
        "id": movie["id"],
        "title": movie["title"],
        "genre": " / ".join([g["name"] for g in movie.get("genre_ids", [])]) or "Unknown",
        "description": movie.get("overview", "No description available"),
        "year": movie.get("release_date", "N/A")[:4],
        "director": "Unknown"
    }

# Create movie HTML page
def create_movie_page(data):
    with open("templates/movie_template.html") as f:
        template = Template(f.read())
    html = template.render(**data)
    os.makedirs(f"movies", exist_ok=True)
    with open(f"movies/{data['id']}.html", "w") as f:
        f.write(html)

# Update homepage
def update_homepage():
    with open("templates/index_template.html") as f:
        template = Template(f.read())
    html = template.render(movies=movies)
    with open("index.html", "w") as f:
        f.write(html)

# Push to GitHub
def push_to_github(movie_data):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(GITHUB_REPO)

    # Add movie page
    path = f"movies/{movie_data['id']}.html"
    with open(path, "r") as f:
        content = f.read()
    try:
        repo.create_file(path, f"Add movie {movie_data['title']}", content, branch=BRANCH)
    except:
        # If file exists, update instead
        file = repo.get_contents(path, ref=BRANCH)
        repo.update_file(path, f"Update movie {movie_data['title']}", content, file.sha, branch=BRANCH)

    # Update homepage
    with open("index.html", "r") as f:
        content = f.read()
    file = repo.get_contents("index.html", ref=BRANCH)
    repo.update_file("index.html", f"Update homepage with {movie_data['title']}", content, file.sha, branch=BRANCH)

if __name__ == "__main__":
    app.run(debug=True)
