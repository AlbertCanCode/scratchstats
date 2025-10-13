from flask import Flask, render_template, request, jsonify
import scratchattach as scratch3
from datetime import datetime 

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

        # --- Date Formatting ---
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
        total_favs = sum(getattr(p, 'favorites', 0) or 0 for p in all_projects)
        total_views = sum(getattr(p, 'views', 0) or 0 for p in all_projects)
        
        most_loved = max(all_projects, key=lambda p: getattr(p, 'loves', 0) or 0) if all_projects else None
        most_viewed = max(all_projects, key=lambda p: getattr(p, 'views', 0) or 0) if all_projects else None

        # --- NEW: Average Project Performance Calculation ---
        project_count = user.project_count()
        # Use 1 for division if project_count is 0 to prevent ZeroDivisionError
        safe_project_count = project_count if project_count > 0 else 1 

        avg_loves = total_loves / safe_project_count
        avg_favorites = total_favs / safe_project_count
        avg_views = total_views / safe_project_count
        # ----------------------------------------------------

        stats_data = {
            "username": user.username,
            "id": user.id,
            "joined": joined_formatted, 
            "country": user.country,
            "about_me": user.about_me, # 👈 User Activity/Status
            "wiwo": user.wiwo,         # 👈 User Activity/Status
            "scratchteam": user.scratchteam, # 👈 User Activity/Status
            "followers": user.follower_count(),
            "following": user.following_count(),
            "project_count": project_count,
            "favorited_projects_count": user.favorites_count(), 
            "total_loves": total_loves,
            "total_favorites_received": total_favs, 
            "total_views": total_views,
            
            # 👈 NEW: Average Project Performance Metrics
            "avg_loves": avg_loves,
            "avg_favorites": avg_favorites,
            "avg_views": avg_views,
            
            "profile_pic": f"https://uploads.scratch.mit.edu/get_image/user/{user.id}_60x60.png",
            
            "most_loved": {
                "title": most_loved.title,
                "loves": getattr(most_loved, 'loves', 0),
                "views": getattr(most_loved, 'views', 0),
                "favorites": getattr(most_loved, 'favorites', 0),
                "id": most_loved.id
            } if most_loved else None,
            
            "most_viewed": {
                "title": most_viewed.title,
                "loves": getattr(most_viewed, 'loves', 0),
                "views": getattr(most_viewed, 'views', 0),
                "favorites": getattr(most_viewed, 'favorites', 0),
                "id": most_viewed.id
            } if most_viewed else None
        }

        return jsonify(stats_data)

    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
