from flask import Flask, render_template, request, jsonify
import scratchattach as scratch3
from datetime import datetime 

app = Flask(__name__)

# Reusable function to fetch and process all stats for a single user
def get_all_stats(username):
    try:
        user = scratch3.get_user(username)
    except:
        # Re-raise to be caught in the API endpoint
        raise Exception("User not found or API error.")

    # --- Date Formatting ---
    joined_datetime = datetime.strptime(user.join_date.split('T')[0], '%Y-%m-%d')
    joined_formatted = joined_datetime.strftime("%B %d, %Y")
    
    # Fetch all projects safely with pagination
    all_projects = []
    offset = 0
    MAX_PROJECTS = 1000
    
    while len(all_projects) < MAX_PROJECTS:
        batch = user.projects(limit=100, offset=offset)
        if not batch:
            break
        all_projects.extend(batch)
        offset += 100

    # Calculate Totals
    total_loves = sum(getattr(p, 'loves', 0) or 0 for p in all_projects)
    total_favs = sum(getattr(p, 'favorites', 0) or 0 for p in all_projects)
    total_views = sum(getattr(p, 'views', 0) or 0 for p in all_projects)
    
    # Identify Top Projects
    most_loved = max(all_projects, key=lambda p: getattr(p, 'loves', 0) or 0) if all_projects else None
    most_viewed = max(all_projects, key=lambda p: getattr(p, 'views', 0) or 0) if all_projects else None
    most_recent = all_projects[0] if all_projects else None

    # Calculate Averages
    project_count = user.project_count()
    safe_project_count = project_count if project_count > 0 else 1 

    avg_loves = total_loves / safe_project_count
    avg_favorites = total_favs / safe_project_count
    avg_views = total_views / safe_project_count

    # Compile Data
    stats_data = {
        "username": user.username,
        "id": user.id,
        "joined": joined_formatted, 
        "country": user.country,
        "about_me": user.about_me,
        "wiwo": user.wiwo,
        "scratchteam": user.scratchteam,
        "followers": user.follower_count(),
        "following": user.following_count(),
        "project_count": project_count,
        "favorited_projects_count": user.favorites_count(), 
        "total_loves": total_loves,
        "total_favorites_received": total_favs, 
        "total_views": total_views,
        
        "avg_loves": avg_loves,
        "avg_favorites": avg_favorites,
        "avg_views": avg_views,
        
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
    return stats_data

# --- New Routing Structure ---

# Homepage: Single User Search
@app.route("/")
def index():
    return render_template("index.html", view_mode="single") 

# Comparison Page: Dual User Search
@app.route("/compare")
def compare_view():
    return render_template("index.html", view_mode="compare") 

# API Endpoint for Fetching Stats (Handles both single and dual requests)
@app.route("/api/stats", methods=["POST"])
def stats_api():
    data = request.form
    username1 = data.get("username1", "").strip()
    username2 = data.get("username2", "").strip()
    
    if not username1:
        return {"error": "Please enter at least one username"}, 400

    results = {}
    errors = {}

    # Fetch User 1
    try:
        results["user1"] = get_all_stats(username1)
    except Exception as e:
        errors["user1"] = f"User '{username1}' not found or API error: {e}"

    # Fetch User 2 (if provided)
    if username2:
        try:
            results["user2"] = get_all_stats(username2)
        except Exception as e:
            errors["user2"] = f"User '{username2}' not found or API error: {e}"
    
    # Final Error Handling
    if not results and (errors.get("user1") or errors.get("user2")):
        # If both fail, return a 500
        return {"error": "Could not find any user. Please check the spelling."}, 500

    # If at least one user was successful, return a 200 with the data and any errors
    return jsonify({"data": results, "errors": errors}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
