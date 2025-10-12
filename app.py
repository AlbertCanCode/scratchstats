from flask import Flask, render_template, request
import requests

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/stats", methods=["POST"])
def stats():
    username = request.form.get("username").strip()
    if not username:
        return {"error": "Please enter a username"}, 400

    try:
        url = f"https://api.scratch.mit.edu/users/{username}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {"error": "User not found"}, 404

        data = response.json()
        stats_data = {
            "username": data.get("username"),
            "id": data.get("id"),
            "joined": data.get("history", {}).get("joined"),
            "followers": data.get("profile", {}).get("stats", {}).get("followers"),
            "following": data.get("profile", {}).get("stats", {}).get("following"),
            "views": data.get("profile", {}).get("stats", {}).get("views"),
            "loves": data.get("profile", {}).get("stats", {}).get("loves"),
            "favorites": data.get("profile", {}).get("stats", {}).get("favorites"),
            "country": data.get("profile", {}).get("country", "Unknown"),
        }
        return stats_data
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
