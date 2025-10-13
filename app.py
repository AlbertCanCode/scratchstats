from flask import Flask, render_template_string, request
import requests

app = Flask(__name__)

# Read HTML from index.html
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
        url = f"https://api.scratch.mit.edu/users/{username}"
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return {"error": "User not found"}, 404

        data = response.json()

        stats_data = {
            "username": data.get("username"),
            "id": data.get("id"),
            "joined": data.get("history", {}).get("joined"),
            "country": data.get("profile", {}).get("country", "Unknown"),
            "followers": data.get("stats", {}).get("followers", 0),
            "following": data.get("stats", {}).get("following", 0),
            "views": data.get("stats", {}).get("views", 0),
            "loves": data.get("stats", {}).get("loves", 0),
            "favorites": data.get("stats", {}).get("favorites", 0),
        }
        return stats_data
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
