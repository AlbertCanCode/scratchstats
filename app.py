import logging
import os
import re
import sqlite3
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

import requests
import scratchattach as scratch3
from flask import Flask, Response, jsonify, render_template, request
from scratchattach.utils import exceptions as scratch_exceptions
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
# Render terminates TLS in front of the app; trust its forwarded headers so
# url_for(..., _external=True) produces https links for the share previews.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

logger = logging.getLogger("scratchstats")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")
MAX_PROJECTS = 1000


# --- Errors ---
class StatsError(Exception):
    status = 502


class UserNotFoundError(StatsError):
    status = 404


class RateLimitedError(StatsError):
    status = 429


class UpstreamError(StatsError):
    status = 502


# --- Bounded, thread-safe TTL cache ---
# Prevents repeated heavy API calls without growing forever.
class TTLCache:
    def __init__(self, ttl, max_size):
        self.ttl = ttl
        self.max_size = max_size
        self._data = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            value, stored_at = entry
            if time.time() - stored_at >= self.ttl:
                del self._data[key]
                return None
            return value

    def set(self, key, value):
        now = time.time()
        with self._lock:
            self._data[key] = (value, now)
            self._data.move_to_end(key)
            expired = [k for k, (_, t) in self._data.items() if now - t >= self.ttl]
            for k in expired:
                del self._data[k]
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)


stats_cache = TTLCache(ttl=300, max_size=500)  # 5 minutes, 500 users


# --- Snapshot history (SQLite) ---
# Set DB_PATH to a path on a persistent disk, otherwise history resets whenever
# the host wipes its filesystem (e.g. Render free tier restarts/deploys).
DB_PATH = os.environ.get(
    "DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "stats.db")
)

LEADERBOARD_METRICS = {
    "followers": "followers",
    "loves": "total_loves",
    "favorites": "total_favorites",
    "views": "total_views",
    "projects": "projects",
}
LEADERBOARD_SIZE = 25
HISTORY_DAYS = 365


def _db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    try:
        conn = _db()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    username        TEXT NOT NULL,
                    day             TEXT NOT NULL,
                    display_name    TEXT NOT NULL,
                    scratch_id      INTEGER,
                    followers       INTEGER NOT NULL,
                    following       INTEGER NOT NULL,
                    projects        INTEGER NOT NULL,
                    total_loves     INTEGER NOT NULL,
                    total_favorites INTEGER NOT NULL,
                    total_views     INTEGER NOT NULL,
                    PRIMARY KEY (username, day)
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not initialise the history database at %s", DB_PATH)


def record_snapshot(stats):
    """Keep one row per user per UTC day; later lookups the same day overwrite it."""
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        conn = _db()
        try:
            conn.execute(
                """
                INSERT INTO snapshots (username, day, display_name, scratch_id, followers,
                    following, projects, total_loves, total_favorites, total_views)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(username, day) DO UPDATE SET
                    display_name = excluded.display_name,
                    scratch_id = excluded.scratch_id,
                    followers = excluded.followers,
                    following = excluded.following,
                    projects = excluded.projects,
                    total_loves = excluded.total_loves,
                    total_favorites = excluded.total_favorites,
                    total_views = excluded.total_views
                """,
                (
                    stats["username"].lower(),
                    day,
                    stats["username"],
                    stats["id"],
                    stats["followers"],
                    stats["following"],
                    stats["project_count"],
                    stats["total_loves"],
                    stats["total_favorites_received"],
                    stats["total_views"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not record snapshot for %s", stats.get("username"))


def get_history(username):
    try:
        conn = _db()
        try:
            rows = conn.execute(
                """
                SELECT day, followers, following, projects, total_loves, total_favorites, total_views
                FROM snapshots WHERE username = ?
                ORDER BY day DESC LIMIT ?
                """,
                (username.lower(), HISTORY_DAYS),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not read history for %s", username)
        return []
    return [
        {
            "day": r["day"],
            "followers": r["followers"],
            "following": r["following"],
            "projects": r["projects"],
            "loves": r["total_loves"],
            "favorites": r["total_favorites"],
            "views": r["total_views"],
        }
        for r in reversed(rows)
    ]


def get_leaderboard(metric):
    column = LEADERBOARD_METRICS[metric]
    try:
        conn = _db()
        try:
            rows = conn.execute(
                f"""
                SELECT s.display_name, s.scratch_id, s.day, s.followers, s.projects,
                       s.total_loves, s.total_favorites, s.total_views
                FROM snapshots s
                JOIN (SELECT username, MAX(day) AS day FROM snapshots GROUP BY username) latest
                  ON s.username = latest.username AND s.day = latest.day
                ORDER BY s.{column} DESC, s.display_name COLLATE NOCASE ASC
                LIMIT ?
                """,
                (LEADERBOARD_SIZE,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("Could not read leaderboard")
        return []
    return [
        {
            "username": r["display_name"],
            "id": r["scratch_id"],
            "updated": r["day"],
            "followers": r["followers"],
            "projects": r["projects"],
            "loves": r["total_loves"],
            "favorites": r["total_favorites"],
            "views": r["total_views"],
        }
        for r in rows
    ]


init_db()


# --- Stats ---
def _format_join_date(raw):
    try:
        return datetime.strptime(raw.split("T")[0], "%Y-%m-%d").strftime("%B %d, %Y")
    except (AttributeError, ValueError):
        return "Unknown"


def _project_summary(project):
    if not project:
        return None
    return {
        "title": project.title,
        "loves": getattr(project, "loves", 0),
        "views": getattr(project, "views", 0),
        "favorites": getattr(project, "favorites", 0),
        "id": project.id,
    }


def _build_stats(user):
    joined_formatted = _format_join_date(user.join_date)

    # Fetch projects with pagination
    all_projects = []
    offset = 0

    while len(all_projects) < MAX_PROJECTS:
        batch = user.projects(limit=100, offset=offset)
        if not batch:
            break
        all_projects.extend(batch)
        offset += 100

    # Stat Calculations
    total_loves = sum(getattr(p, "loves", 0) or 0 for p in all_projects)
    total_favs = sum(getattr(p, "favorites", 0) or 0 for p in all_projects)
    total_views = sum(getattr(p, "views", 0) or 0 for p in all_projects)

    most_loved = max(all_projects, key=lambda p: getattr(p, "loves", 0) or 0) if all_projects else None
    most_viewed = max(all_projects, key=lambda p: getattr(p, "views", 0) or 0) if all_projects else None
    most_recent = all_projects[0] if all_projects else None

    followers = user.follower_count()
    following = user.following_count()
    ff_ratio = round(followers / following, 2) if following > 0 else followers

    days_since_last_project = "N/A"
    most_recent_activity = "N/A"

    if most_recent and getattr(most_recent, "last_modified", None):
        try:
            last_modified_dt = datetime.strptime(
                most_recent.last_modified.split(".")[0], "%Y-%m-%dT%H:%M:%S"
            )
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            days_since_last_project = max((now_utc - last_modified_dt).days, 0)
            most_recent_activity = last_modified_dt.strftime("%B %d, %Y")
        except (ValueError, AttributeError):
            pass

    project_count = user.project_count()
    safe_project_count = project_count if project_count > 0 else 1

    return {
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
        "most_loved": _project_summary(most_loved),
        "most_viewed": _project_summary(most_viewed),
        "most_recent": _project_summary(most_recent),
    }


def get_all_stats(username):
    key = username.lower()

    cached = stats_cache.get(key)
    if cached is not None:
        return cached

    not_found = UserNotFoundError(f"User '{username}' not found on Scratch.")
    if not USERNAME_RE.match(username):
        raise not_found

    try:
        user = scratch3.get_user(username)
        # scratchattach sometimes returns an empty object for unknown users
        if user.id is None:
            raise not_found
        stats = _build_stats(user)
    except StatsError:
        raise
    except scratch_exceptions.UserNotFound:
        raise not_found
    except scratch_exceptions.RateLimitedError:
        raise RateLimitedError("Scratch is rate limiting us right now. Please try again in a minute.")
    except Exception:
        logger.exception("Failed to fetch stats for %s", username)
        raise UpstreamError("Couldn't reach Scratch right now. Please try again shortly.")

    stats_cache.set(key, stats)
    record_snapshot(stats)
    return stats


# --- Pages ---
def _clean_username(value):
    value = (value or "").strip()
    return value if USERNAME_RE.match(value) else ""


def _share_description(username):
    cached = stats_cache.get(username.lower())
    if cached:
        return (
            f"{cached['username']} on Scratch: {cached['followers']:,} followers, "
            f"{cached['total_loves']:,} loves, {cached['total_views']:,} views."
        )
    return f"See {username}'s Scratch stats."


@app.route("/")
def index():
    return render_template("index.html", view_mode="single", active="single")


@app.route("/u/<username>")
def user_page(username):
    username = _clean_username(username)
    page_title = f"{username}'s Scratch Stats" if username else "Scratch Stats"
    return render_template(
        "index.html",
        view_mode="single",
        active="single",
        prefill1=username,
        page_title=page_title,
        page_description=_share_description(username) if username else None,
    )


@app.route("/compare")
def compare_view():
    return render_template("index.html", view_mode="compare", active="compare")


@app.route("/compare/<username1>/<username2>")
def compare_users_page(username1, username2):
    username1, username2 = _clean_username(username1), _clean_username(username2)
    both = bool(username1 and username2)
    return render_template(
        "index.html",
        view_mode="compare",
        active="compare",
        prefill1=username1,
        prefill2=username2,
        page_title=f"{username1} vs {username2} - Scratch Stats" if both else "Compare Scratch Users",
        page_description=f"Compare {username1} and {username2} on Scratch." if both else None,
    )


@app.route("/leaderboard")
def leaderboard_page():
    return render_template("leaderboard.html", active="leaderboard", page_title="Leaderboard - Scratch Stats")


# --- API ---
@app.route("/api/stats", methods=["POST"])
def stats_api():
    data = request.form
    username1 = data.get("username1", "").strip()
    username2 = data.get("username2", "").strip()

    if not username1:
        return jsonify({"error": "Please enter at least one username"}), 400

    results = {}
    errors = {}
    error_statuses = []

    def fetch_user(u_name, key):
        try:
            results[key] = get_all_stats(u_name)
        except StatsError as e:
            errors[key] = str(e)
            error_statuses.append(e.status)

    fetch_user(username1, "user1")
    if username2:
        fetch_user(username2, "user2")

    if not results:
        if all(status == 404 for status in error_statuses):
            return jsonify({"error": "No valid users found. Check spelling.", "details": errors}), 404
        status = 429 if 429 in error_statuses else 502
        message = next(m for m, s in zip(errors.values(), error_statuses) if s == status)
        return jsonify({"error": message, "details": errors}), status

    return jsonify({"data": results, "errors": errors}), 200


@app.route("/api/history/<username>")
def history_api(username):
    if not USERNAME_RE.match(username):
        return jsonify({"points": []})
    return jsonify({"points": get_history(username)})


@app.route("/api/leaderboard")
def leaderboard_api():
    metric = request.args.get("metric", "followers")
    if metric not in LEADERBOARD_METRICS:
        return jsonify({"error": "Unknown metric"}), 400
    return jsonify({"metric": metric, "users": get_leaderboard(metric)})


# Same-origin proxy so the "download as image" export isn't blocked by CORS.
# Only fixed Scratch hosts and numeric ids are ever requested.
IMAGE_SOURCES = {
    "user": "https://uploads.scratch.mit.edu/get_image/user/{id}_90x90.png",
    "project": "https://cdn2.scratch.mit.edu/get_image/project/{id}_144x108.png",
}
MAX_IMAGE_BYTES = 1_000_000


def _proxy_image(kind, object_id):
    try:
        upstream = requests.get(IMAGE_SOURCES[kind].format(id=object_id), timeout=10)
    except requests.RequestException:
        return Response(status=502)
    content_type = upstream.headers.get("Content-Type", "")
    if (
        upstream.status_code != 200
        or not content_type.startswith("image/")
        or len(upstream.content) > MAX_IMAGE_BYTES
    ):
        return Response(status=404)
    return Response(
        upstream.content,
        mimetype=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.route("/img/user/<int:user_id>")
def proxy_user_image(user_id):
    return _proxy_image("user", user_id)


@app.route("/img/project/<int:project_id>")
def proxy_project_image(project_id):
    return _proxy_image("project", project_id)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
