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

        projects = user.projects(limit=100, offset=0)
        total_loves = sum(p.loves for p in projects) if projects else 0
        total_favs = sum(p.favorites for p in projects) if projects else 0
        total_views = sum(p.views for p in projects) if projects else 0
        most_loved = max(projects, key=lambda p: p.loves) if projects else None

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
