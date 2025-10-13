from flask import Flask, render_template_string, request
import scratchattach as scratch3

app = Flask(__name__)

with open("index.html", "r") as f:
    HTML = f.read()

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/stats", methods=["POST"])
def stats():
    username = request.form.get("username", "").strip()
    if not username:
        return {"error": "Please enter a username"}, 400

    try:
        user = scratch3.get_user(username)

        # Fetch all projects safely with pagination
        all_projects = []
        offset = 0
        while True:
            batch = user.projects(limit=100, offset=offset)
            if not batch:
                break
            all_projects.extend(batch)
            offset += 100

        total_loves = sum(p.loves or 0 for p in all_projects)
        total_favs = sum(p.favorites or 0 for p in all_projects)
        total_views = sum(p.views or 0 for p in all_projects)
        most_loved = max(all_projects, key=lambda p: p.loves or 0) if all_projects else None

        stats_data = {
            "username": user.username,
            "id": user.id,
            "joined": user.join_date,
            "country": user.country,
            "about_me": user.about_me,
            "wiwo": user.wiwo,
            "scratchteam": user.scratchteam,
            "followers": user.follower_count(),
            "following": user.following_count(),
            "project_count": user.project_count(),
            "favorites_count": user.favorites_count(),
            "total_loves": total_loves,
            "total_favorites": total_favs,
            "total_views": total_views,
            "most_loved": {
                "title": most_loved.title,
                "loves": most_loved.loves,
                "views": most_loved.views,
                "favorites": most_loved.favorites,
                "id": most_loved.id
            } if most_loved else None
        }

        return stats_data

    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
