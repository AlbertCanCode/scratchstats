from flask import Flask, render_template, request, jsonify
import scratchattach as scratch3
from datetime import datetime, timedelta
import time

app = Flask(__name__)

# --- Simple In-Memory Cache ---
# Stores results to prevent repeated heavy API calls
stats_cache = {}
CACHE_DURATION = 300  # 5 minutes in seconds

def get_all_stats(username):
    current_time = time.time()
    
    # Check if we have a recent cached version
    if username in stats_cache:
        cached_data, timestamp = stats_cache[username]
        if current_time - timestamp < CACHE_DURATION:
            return cached_data

    try:
        user = scratch3.get_user(username)
        # Check if user actually exists (scratchattach sometimes returns an empty object)
        if user.id is None:
            raise ValueError("User not found")
    except Exception:
        raise Exception(f"User '{username}' not found on Scratch.")

    # --- Date Formatting ---
    joined_datetime = datetime.strptime(user.join_date.split('T')[0], '%Y-%m-%d')
    joined_formatted = joined_datetime.strftime("%B %d, %Y")
    
    # Fetch projects with pagination
    all_projects = []
    offset = 0
    MAX_PROJECTS = 1000
    
    while len(all_projects) < MAX_PROJECTS:
        batch = user.projects(limit=100, offset=offset)
        if not batch:
            break
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
    following = user.following_count()
    ff_ratio = round(followers / following, 2) if following > 0 else followers

    days_since_last_project = "N/A"
    most_recent_activity = "N/A" 
    
    if most_recent and getattr(most_recent, 'last_modified', None):
        try:
            last_modified_dt = datetime.strptime(most_recent.last_modified.split('.')[0], '%Y-%m-%dT%H:%M:%S')
            time_difference = datetime.now() - last_modified_dt
            days_since_last_project = time_difference.days
            most_recent_activity = last_modified_dt.strftime("%B %d, %Y")
        except:
            pass

    project_count = user.project_count()
    safe_project_count = project_count if project_count > 0 else 1 

    stats_data = {
        "username": user.username,
        "id": user.id,
        "joined": joined_formatted, 
        "country": user.country,
        "about_me": user.about_me,
        "wiwo": user.wiwo,
        "scratchteam": user.scratchteam,
        "followers": followers,
        "following": following,
        "ff_ratio": ff_ratio,
        "project_count": project_count,
        "favorited_projects_count": user.favorites_count(), 
        "total_loves": total_loves,
        "total_favorites_received": total_favs, 
        "total_views": total_views,
        "avg_loves": round(total_loves / safe_project_count, 2),
        "avg_favorites": round(total_favs / safe_project_count, 2),
        "avg_views": round(total_views / safe_project_count, 2),
        "days_since_last_project": days_since_last_project,
        "most_recent_activity": most_recent_activity,
        "profile_pic": f"https://uploads.scratch.mit.edu/get_image/user/{user.id}_90x90.png",
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
        } if most_viewed else None,
        "most_recent": {
            "title": most_recent.title,
            "loves": getattr(most_recent, 'loves', 0),
            "views": getattr(most_recent, 'views', 0),
            "favorites": getattr(most_recent, 'favorites', 0),
            "id": most_recent.id
        } if most_recent else None
    }
    
    # Store in cache before returning
    stats_cache[username] = (stats_data, current_time)
    return stats_data

@app.route("/")
def index():
    return render_template("index.html", view_mode="single") 

@app.route("/compare")
def compare_view():
    return render_template("index.html", view_mode="compare") 

@app.route("/api/stats", methods=["POST"])
def stats_api():
    data = request.form
    username1 = data.get("username1", "").strip().lower() # Normalize to lowercase for caching
    username2 = data.get("username2", "").strip().lower()
    
    if not username1:
        return jsonify({"error": "Please enter at least one username"}), 400

    results = {}
    errors = {}

    # Helper to fetch and categorize errors
    def fetch_user(u_name, key):
        try:
            results[key] = get_all_stats(u_name)
        except Exception as e:
            errors[key] = str(e)

    fetch_user(username1, "user1")
    if username2:
        fetch_user(username2, "user2")
    
    # If no users were found at all, return 404
    if not results:
        return jsonify({"error": "No valid users found. Check spelling.", "details": errors}), 404

    return jsonify({"data": results, "errors": errors}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
