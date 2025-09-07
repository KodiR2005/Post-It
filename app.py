from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import secrets
from pyngrok import conf, ngrok
from threading import Thread
import webbrowser
import os
import requests
import sqlite3
from sqlite3 import IntegrityError
from colorama import Fore, init
from datetime import datetime
from werkzeug.utils import secure_filename
import mimetypes

# ================= CONFIG =================
GOOGLE_MAPS_API_KEY = "AIzaSyCrJvJAfUmGVWYSPptbMm3fl-j2mlElKJA"
conf.get_default().log_level = "ERROR"
os.system("")  # Enable ANSI colors in terminal
init(autoreset=True)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Upload config
UPLOAD_FOLDER = os.path.join("static", "uploads")  # ----------- set upload folder here ------------
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webm'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ================= DATABASE =================

def init_db():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT,
            ipv4 TEXT,
            latitude REAL,
            longitude REAL,
            name TEXT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            phone TEXT,
            password TEXT,
            bio TEXT,
            profile_pic TEXT,
            browser_info TEXT,
            cookies_enabled TEXT,
            language TEXT,
            platform TEXT,
            screen_size TEXT,
            timezone TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER,
            following_id INTEGER,
            UNIQUE(follower_id, following_id)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content_type TEXT,
            content TEXT,
            caption TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            comment TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            post_id INTEGER,
            UNIQUE(user_id, post_id)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            theme TEXT DEFAULT 'light',
            font_size INTEGER DEFAULT 16,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """)
        conn.commit()

init_db()


# ================= ROUTES =================

@app.route("/")
def index():
    return render_template("index.html")


# ---------- Signup ----------
@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        name = data.get("name", "").strip()
        username = data.get("username", "").strip()  # may be empty
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()
        lat = data.get("lat")
        lng = data.get("lng")
        password = data.get("password", "").strip()
        user_info = data.get("userInfo", {})

        if not name or not email or not password:
            return jsonify(status="error", message="Name, email, and password are required.")

        # Get raw IP
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        # Attempt to extract IPv4
        ipv4 = None
        try:
            # If comma-separated list (proxies), take first
            user_ip_clean = user_ip.split(",")[0].strip()
            if ":" not in user_ip_clean:  # IPv4
                ipv4 = user_ip_clean
            else:
                # Try to get public IPv4 via external service
                ipv4 = requests.get("https://api.ipify.org").text
        except:
            ipv4 = None  # leave NULL if failed

        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()

            # Check email uniqueness
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                return jsonify(status="error", message="Email already registered.")

            # Only check username if provided
            db_username = username if username else None
            if db_username:
                cursor.execute("SELECT id FROM users WHERE username = ?", (db_username,))
                if cursor.fetchone():
                    return jsonify(status="error", message="Username already taken.")

            cursor.execute("""
                INSERT INTO users (
                    ip, ipv4, latitude, longitude, name, username, email, phone, password,
                    browser_info, cookies_enabled, language, platform, screen_size, timezone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_ip, ipv4, lat, lng, name, db_username, email, phone, password,
                user_info.get("Browser Info"),
                str(user_info.get("Cookies Enabled")),
                user_info.get("Language"),
                user_info.get("Platform"),
                user_info.get("Screen Size"),
                user_info.get("Timezone")
            ))

            user_id = cursor.lastrowid
            conn.commit()

        session['user_id'] = user_id
        return jsonify(status="success")

    except IntegrityError:
        return jsonify(status="error", message="Username or email already exists.")
    except Exception as e:
        return jsonify(status="error", message=str(e))




# ---------- Login ----------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ? AND password = ?", (email, password))
        user = cursor.fetchone()
    if user:
        session['user_id'] = user[0]
        return jsonify(status="success")
    else:
        return jsonify(status="error", message="Invalid email or password.")



# ================= UPDATED PROFILE ROUTE =================

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Get user info
    cursor.execute("SELECT username, name, bio, profile_pic FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    # --- FIXED followers / following counts ---
    cursor.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (user_id,))
    followers_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM follows WHERE follower_id=?", (user_id,))
    following_count = cursor.fetchone()[0]

    # User settings
    cursor.execute("SELECT theme, font_size FROM user_settings WHERE user_id=?", (user_id,))
    settings = cursor.fetchone()
    conn.close()

    theme = settings[0] if settings else "light"
    font_size = settings[1] if settings else 16

    return render_template(
        "profile.html",
        username=user[0] if user[0] else "",  # ----------- profile.py route ------------
        name=user[1] if user[1] else "",
        bio=user[2] if user[2] else "",
        profile_pic=user[3] if user[3] else "",
        user_id=user_id,
        theme=theme,
        font_size=font_size,
        followers=followers_count,
        following=following_count,
        followers_url=url_for("followers_list", user_id=user_id),
        following_url=url_for("following_list", user_id=user_id)
    )




# ---------- Edit Profile ----------

@app.route("/profile/edit", methods=["GET", "POST"])
def edit_profile():
    if "user_id" not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        bio = request.form.get("bio")
        password = request.form.get("password")
        file = request.files.get("profile_pic")
        profile_pic_filename = None
        if file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                filename = f"{timestamp}_{filename}"
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                dest = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(dest)
                profile_pic_filename = filename
        if username:
            cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, user_id))
            if cursor.fetchone():
                conn.close()
                return jsonify(status="error", message="Username already taken.")
        update_fields = [("name", name), ("username", username), ("bio", bio)]
        if password:
            update_fields.append(("password", password))
        if profile_pic_filename:
            update_fields.append(("profile_pic", profile_pic_filename))
        set_clause = ", ".join(f"{col}=?" for col, _ in update_fields)
        values = [val for _, val in update_fields] + [user_id]
        cursor.execute(f"UPDATE users SET {set_clause} WHERE id=?", values)
        conn.commit()
        conn.close()
        return jsonify(status="success")
    cursor.execute("SELECT name, username, bio, profile_pic FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return redirect(url_for('index'))
    name, username, bio, profile_pic = user
    return render_template("edit_profile.html", name=name, username=username, bio=bio, profile_pic=profile_pic)



# ---------- Search Other User ----------

@app.route("/search_users")
def search_users():
    if "user_id" not in session:
        return jsonify(status="error", message="Not logged in.")
    query = request.args.get("username", "").strip()
    if not query:
        return jsonify(status="success", users=[])
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users WHERE username LIKE ?", (f"%{query}%",))
    users = [{"id": row[0], "username": row[1]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(status="success", users=users)



# ---------- View Other User ----------

@app.route("/view_user/<int:user_id>")
def view_user(user_id):
    if "user_id" not in session:
        return redirect(url_for("index"))
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, username, bio, profile_pic FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return redirect(url_for("profile"))
    name, username, bio, profile_pic = user
    cursor.execute("SELECT COUNT(*) FROM follows WHERE following_id = ?", (user_id,))
    followers_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM follows WHERE follower_id = ?", (user_id,))
    following_count = cursor.fetchone()[0]
    current_user = session["user_id"]
    cursor.execute("SELECT id FROM follows WHERE follower_id = ? AND following_id = ?", (current_user, user_id))
    is_following = cursor.fetchone() is not None
    conn.close()
    return render_template("view_user.html",
                       user_id=user_id,
                       name=name,
                       username=username,
                       bio=bio,
                       profile_pic=profile_pic,
                       followers=followers_count,
                       following=following_count,
                       is_following=is_following)


# ---------- Follow / Unfollow ----------

@app.route("/follow/<int:user_id>", methods=["POST"])
def follow_user(user_id):
    if "user_id" not in session:
        return jsonify(status="error", message="Not logged in.")
    current_user = session["user_id"]
    if current_user == user_id:
        return jsonify(status="error", message="You cannot follow yourself.")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM follows WHERE follower_id=? AND following_id=?", (current_user, user_id))
    if cursor.fetchone():
        cursor.execute("DELETE FROM follows WHERE follower_id=? AND following_id=?", (current_user, user_id))
        action = "unfollowed"
    else:
        cursor.execute("INSERT OR IGNORE INTO follows (follower_id, following_id) VALUES (?, ?)", (current_user, user_id))
        action = "followed"
    
    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM follows WHERE following_id=?", (user_id,))
    followers_count = cursor.fetchone()[0]
    conn.close()
    return jsonify(status="success", action=action, followers=followers_count)

# ---------- Feed ----------

@app.route("/feed")
def feed():
    if "user_id" not in session:
        return redirect(url_for("index"))
    user_id = session["user_id"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.id, p.user_id, u.username, u.profile_pic, p.content_type, p.content, p.caption, p.timestamp
        FROM posts p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.timestamp DESC
    """)
    rows = cursor.fetchall()

    cursor.execute("SELECT theme, font_size FROM user_settings WHERE user_id=?", (user_id,))
    settings = cursor.fetchone()
    conn.close()

    theme = settings[0] if settings else "light"
    font_size = settings[1] if settings else 16

    posts = []
    for row in rows:
        pid, uid, username, profile_pic, content_type, content, caption, timestamp = row
        mime = mimetypes.guess_type(content)[0] if content else ""
        posts.append({
            "id": pid,
            "user_id": uid,
            "username": username,
            "profile_pic": profile_pic,
            "content_type": content_type,
            "content": content,
            "caption": caption,
            "timestamp": timestamp,
            "mime": mime
        })

    return render_template("feed.html", posts=posts, theme=theme, font_size=font_size)



# ---------- Create Post ----------

@app.route("/feed/post", methods=["POST"])
def create_post():
    if "user_id" not in session:
        return jsonify(status="error", message="Not logged in.")
    user_id = session["user_id"]

    if request.is_json:
        data = request.get_json()
        content_type = data.get("content_type")
        caption = data.get("caption", "").strip()
        content = data.get("content", "").strip()
        if not content:
            return jsonify(status="error", message="Content cannot be empty.")
    else:
        content_type = request.form.get("content_type")
        caption = request.form.get("caption", "").strip()
        if content_type == "text":
            content = request.form.get("content", "").strip()
            if not content:
                return jsonify(status="error", message="Content cannot be empty.")
        else:
            if 'file' not in request.files:
                return jsonify(status="error", message="No file uploaded.")
            file = request.files['file']
            if file.filename == "":
                return jsonify(status="error", message="No file selected.")
            if not allowed_file(file.filename):
                return jsonify(status="error", message="File type not allowed.")
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            filename = f"{timestamp}_{filename}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            dest = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(dest)
            content = filename

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO posts (user_id, content_type, content, caption)
        VALUES (?, ?, ?, ?)
    """, (user_id, content_type, content, caption))
    conn.commit()
    conn.close()
    return jsonify(status="success")



# ---------- Post Comments ----------

@app.route("/feed/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    if "user_id" not in session:
        return jsonify(status="error", message="Not logged in.")
    user_id = session["user_id"]
    data = request.get_json()
    comment = data.get("comment", "").strip()
    if not comment:
        return jsonify(status="error", message="Comment cannot be empty.")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (post_id, user_id, comment) VALUES (?, ?, ?)",
        (post_id, user_id, comment)
    )
    conn.commit()

    cursor.execute("""
        SELECT c.comment, u.username
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id=?
        ORDER BY c.timestamp ASC
    """, (post_id,))
    comments = [{"username": u, "comment": c} for c, u in cursor.fetchall()]
    conn.close()

    return jsonify(status="success", comments=comments)



# ---------- Save / Unsave Post ----------

@app.route("/post/save/<int:post_id>", methods=["POST"])
def save_post(post_id):
    if "user_id" not in session:
        return jsonify(status="error", message="Not logged in.")
    user_id = session["user_id"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM saved_posts WHERE user_id=? AND post_id=?", (user_id, post_id))
    if cursor.fetchone():
        cursor.execute("DELETE FROM saved_posts WHERE user_id=? AND post_id=?", (user_id, post_id))
        action = "unsaved"
    else:
        cursor.execute("INSERT OR IGNORE INTO saved_posts (user_id, post_id) VALUES (?, ?)", (user_id, post_id))
        action = "saved"
    conn.commit()
    conn.close()
    return jsonify(status="success", action=action)



# ---------- Saved Posts ----------

@app.route("/profile/saved")
def saved_posts():
    if "user_id" not in session:
        return redirect(url_for("index"))
    user_id = session["user_id"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.user_id, u.username, u.profile_pic, p.content_type, p.content, p.caption, p.timestamp
        FROM saved_posts s
        JOIN posts p ON s.post_id = p.id
        JOIN users u ON p.user_id = u.id
        WHERE s.user_id=?
        ORDER BY p.timestamp DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    posts = []
    for row in rows:
        pid, uid, username, profile_pic, content_type, content, caption, timestamp = row
        mime = mimetypes.guess_type(content)[0] if content else ''
        posts.append({
            'id': pid,
            'user_id': uid,
            'username': username,
            'profile_pic': profile_pic,
            'content_type': content_type,
            'content': content,
            'caption': caption,
            'timestamp': timestamp,
            'mime': mime
        })

    return render_template("saved_posts.html", posts=posts)



# ---------- Profile Settings ----------

@app.route("/profile/settings", methods=["GET", "POST"])
def profile_settings():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    if request.method == "POST":
        theme = request.form.get("theme", "light")
        font_size = request.form.get("font_size", 16)

        cursor.execute("""
            INSERT INTO user_settings (user_id, theme, font_size)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                theme=excluded.theme,
                font_size=excluded.font_size
        """, (user_id, theme, font_size))
        conn.commit()
        conn.close()
        flash("Settings updated!", "success")
        return redirect(url_for("profile"))

    cursor.execute("SELECT theme, font_size FROM user_settings WHERE user_id=?", (user_id,))
    settings = cursor.fetchone()
    conn.close()

    theme, font_size = settings if settings else ("light", 16)
    return render_template("settings.html", theme=theme, font_size=font_size)



# ---------- My Posts ----------

@app.route("/profile/posts")
def my_posts():
    if "user_id" not in session:
        return redirect(url_for("index"))
    user_id = session["user_id"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, content_type, content, caption, timestamp
        FROM posts
        WHERE user_id=?
        ORDER BY timestamp DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    posts = []
    for row in rows:
        pid, content_type, content, caption, timestamp = row
        posts.append({
            "id": pid,
            "content_type": content_type,
            "content": content,
            "caption": caption,
            "timestamp": timestamp
        })

    return render_template("my_posts.html", posts=posts)



# ---------- Logout ----------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))




# ================= FOLLOWERS / FOLLOWING ROUTES =================

@app.route("/followers/<int:user_id>")
def followers_list(user_id):
    """List all users who follow the given user_id"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username FROM users u
        JOIN follows f ON f.follower_id = u.id
        WHERE f.following_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    # Convert tuples to dicts for easier template usage
    followers = [{"id": u[0], "username": u[1]} for u in rows]

    return render_template("followers_list.html", followers=followers)


@app.route("/following/<int:user_id>")
def following_list(user_id):
    """List all users that the given user_id is following"""
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username FROM users u
        JOIN follows f ON f.following_id = u.id
        WHERE f.follower_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    # Convert tuples to dicts for easier template usage
    following = [{"id": u[0], "username": u[1]} for u in rows]

    return render_template("following_list.html", following=following)







# ---------- Fetch Post Comments ----------
@app.route("/post/comments/<int:post_id>")
def get_post_comments(post_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.comment, u.username
        FROM comments c
        JOIN users u ON c.user_id = u.id
        WHERE c.post_id = ?
        ORDER BY c.timestamp ASC
    """, (post_id,))
    comments = [{"username": u, "comment": c} for c, u in cursor.fetchall()]
    conn.close()
    return jsonify(comments)


# ---------- Delete Post ----------
@app.route("/post/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    if "user_id" not in session:
        return jsonify(status="error", message="Not logged in.")
    user_id = session["user_id"]

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Check if the post belongs to the current user
    cursor.execute("SELECT user_id FROM posts WHERE id=?", (post_id,))
    post = cursor.fetchone()
    if not post:
        conn.close()
        return jsonify(status="error", message="Post does not exist.")
    if post[0] != user_id:
        conn.close()
        return jsonify(status="error", message="You cannot delete this post.")

    # Delete post, comments, saved entries
    cursor.execute("DELETE FROM posts WHERE id=?", (post_id,))
    cursor.execute("DELETE FROM comments WHERE post_id=?", (post_id,))
    cursor.execute("DELETE FROM saved_posts WHERE post_id=?", (post_id,))
    conn.commit()
    conn.close()

    return jsonify(status="success")





# ================= START APP =================

def run_flask():
    app.run(port=5000)


def start_ngrok():
    tunnel = ngrok.connect(5000)
    print(Fore.BLUE + f"Ngrok URL: {tunnel.public_url}")
    webbrowser.open(tunnel.public_url)

# ================= MAIN =================
if __name__ == "__main__":
    # Start ngrok tunnel in background
    Thread(target=start_ngrok, daemon=True).start()
    # Start Flask app
    run_flask() 