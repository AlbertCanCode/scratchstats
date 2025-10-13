from flask import Flask, render_template, request, jsonify
import scratchattach as scratch3
from datetime import datetime # 👈 IMPORT DATETIME

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stats", methods=["POST"])
def stats():
    username = request.form.get("username", "").strip()
    if not username:
        return {"error": "Please enter a username"}, 400

    try:
        user = scratch3.get_user(username)

        # --- Date Formatting Fix ---
        # scratchattach returns the date like 'YYYY-MM-DDThh:mm:ss.msZ'. 
        # We need to parse and reformat it.
        # Use split('T')[0] to get only the date part 'YYYY-MM-DD'
        joined_datetime = datetime.strptime(user.join_date.split('T')[0], '%Y-%m-%d')
        joined_formatted = joined_datetime.strftime("%B %d, %Y")
        # ---------------------------

        # Fetch all projects safely with pagination
        all_projects = []
        offset = 0
        MAX_PROJECTS = 1000  # Reasonable limit
        
        while len(all_projects) < MAX_PROJECTS:
            batch = user.projects(limit=100, offset=offset)
            if not batch:
                break
            all_projects.extend(batch)
            offset += 100

        total_loves = sum(getattr(p, 'loves', 0) or 0 for p in all_projects)
        # --- Total Favorites Fix ---
        # This now correctly aggregates the favorites from all *user's projects*, 
        # not the count of projects the *user has favorited* (which is favorites_count()).
        total_favs = sum(getattr(p, 'favorites', 0) or 0 for p in all_projects)
        # The user's count of projects they favorited is still available as user.favorites_count()
        # ---------------------------
        total_views = sum(getattr(p, 'views', 0) or 0 for p in all_projects)
        most_loved = max(all_projects, key=lambda p: getattr(p, 'loves', 0) or 0) if all_projects else None

        stats_data = {
            "username": user.username,
            "id": user.id,
            # Use the newly formatted date for the frontend
            "joined": joined_formatted, 
            "country": user.country,
            "about_me": user.about_me,
            "wiwo": user.wiwo,
            "scratchteam": user.scratchteam,
            "followers": user.follower_count(),
            "following": user.following_count(),
            "project_count": user.project_count(),
            # Renamed to reflect what it tracks: the count of projects the user has favorited
            "favorited_projects_count": user.favorites_count(), 
            "total_loves": total_loves,
            # This is the new, correct aggregate favorite count for all their projects
            "total_favorites_received": total_favs, 
            "total_views": total_views,
            "profile_pic": f"https://uploads.scratch.mit.edu/get_image/user/{user.id}_60x60.png",
            "most_loved": {
                "title": most_loved.title,
                "loves": getattr(most_loved, 'loves', 0),
                "views": getattr(most_loved, 'views', 0),
                "favorites": getattr(most_loved, 'favorites', 0),
                "id": most_loved.id
            } if most_loved else None
        }

        return jsonify(stats_data)

    except Exception as e:
        # User not found or other API error
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
