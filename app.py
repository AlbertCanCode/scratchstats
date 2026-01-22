from flask import Flask, render_template, request, jsonify
import scratchattach as scratch3
from datetime import datetime
import time

app = Flask(__name__)

# --- Simple In-Memory Cache ---
stats_cache = {}
CACHE_DURATION = 300  # 5 minutes

def get_all_stats(username):
    current_time = time.time()
    username_key = username.lower().strip()
    
    # Check Cache
    if username_key in stats_cache:
        cached_data, timestamp = stats_cache[username_key]
        if current_time - timestamp < CACHE_DURATION:
            return cached_data

    try:
        user = scratch3.get_user(username)
        if user.id is None:
            raise ValueError("User not found")
    except Exception:
        raise Exception(f"User '{username}' not found.")

    # Fetch projects with pagination
    all_projects = []
    offset = 0
    while len(all_projects) < 1000:
        batch = user.projects(limit=100, offset=offset)
        if not batch: break
        all_projects.extend(batch)
        offset += 100

    # Stat Calculations
    total_loves = sum(getattr(p, 'loves', 0) or 0 for p in all_projects)
    total_favs = sum(getattr(p, 'favorites', 0) or 0 for p in all_projects)
    total_views = sum(getattr(p, 'views', 0) or 0 for p in all_projects)
    
    most_loved = max(all_projects, key=lambda p: getattr(p, 'loves', 0) or 0) if all_projects else None
    most_viewed = max(all_projects, key=lambda p: getattr(p, 'views', 0) or 0) if all_projects else None
    most_recent = all_projects[0] if all_projects else None

    followers = user.follower_count()
    project_count = user.project_count()

    stats_data = {
        "username": user.username,
        "id": user.id,
        "joined": user.join_date,
        "followers": followers,
        "following": user.following_count(),
        "project_count": project_count,
        "total_loves": total_loves,
        "total_favorites": total_favs,
        "total_views": total_views,
        "avg_loves": round(total_loves / project_count, 2) if project_count > 0 else 0,
        "profile_pic": f"https://uploads.scratch.mit.edu/get_image/user/{user.id}_90x90.png",
        "most_loved": {"title": most_loved.title, "loves": most_loved.loves, "id": most_loved.id} if most_loved else None,
        "most_viewed": {"title": most_viewed.title, "views": most_viewed.views, "id": most_viewed.id} if most_viewed else None
    }
    
    stats_cache[username_key] = (stats_data, current_time)
    return stats_data

@app.route("/")
def index():
    return render_template("index.html", view_mode="single") 

@app.route("/compare")
def compare_view():
    return render_template("index.html", view_mode="compare") 

@app.route("/api/stats", methods=["POST"])
def stats_api():
    u1 = request.form.get("username1")
    u2 = request.form.get("username2")
    results = {}
    try:
        if u1: results["user1"] = get_all_stats(u1)
        if u2: results["user2"] = get_all_stats(u2)
        return jsonify({"data": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 404

if __name__ == "__main__":
    app.run(debug=True)
