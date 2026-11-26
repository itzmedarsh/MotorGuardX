import os
import html
import time
import hmac
import secrets
import sqlite3
import logging
from pathlib import Path
from collections import defaultdict
from logging.handlers import RotatingFileHandler

from aiohttp import web
from aiohttp_session import get_session
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from dotenv import load_dotenv

load_dotenv()


MODAL_TEMPLATE = r"""
<div class="modal-backdrop" id="noticeModal" role="presentation">
  <div class="modal-card" role="alertdialog" aria-modal="true"
       aria-labelledby="modalTitle" aria-describedby="modalMessage">
    <div class="modal-icon">!</div>
    <h2 id="modalTitle">{title}</h2>
    <p id="modalMessage">{message}</p>
    <button type="button" class="modal-button" id="modalClose">Okay</button>
  </div>
</div>
<style>
.modal-backdrop{{position:fixed;inset:0;background:rgba(0,0,0,.72);
display:flex;align-items:center;justify-content:center;padding:20px;z-index:9999;
animation:fadeIn .18s ease-out}}
.modal-card{{width:100%;max-width:390px;background:#111a28;border:1px solid #35445c;
border-radius:18px;padding:28px;text-align:center;box-shadow:0 24px 80px #000b;
animation:popIn .2s ease-out}}
.modal-icon{{width:48px;height:48px;border-radius:50%;margin:0 auto 14px;
display:grid;place-items:center;background:#512b31;color:#ff7777;font-size:26px;font-weight:800}}
.modal-card h2{{margin:0 0 10px;color:#f4f7fb;font-size:21px}}
.modal-card p{{margin:0 0 22px;color:#aebbd0;line-height:1.5;font-size:14px}}
.modal-button{{width:100%;border:0;border-radius:9px;background:#ed4545;color:white;
padding:12px 16px;font-weight:700;cursor:pointer}}
.modal-button:hover{{background:#ff5b5b}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes popIn{{from{{opacity:0;transform:translateY(10px) scale(.96)}}to{{opacity:1;transform:translateY(0) scale(1)}}}}
</style>
<script>
(function(){{
  const backdrop = document.getElementById("noticeModal");
  const closeButton = document.getElementById("modalClose");
  function closeModal() {{
    if (backdrop) backdrop.remove();
    const url = new URL(window.location.href);
    url.searchParams.delete("error");
    window.history.replaceState({{}}, document.title, url.pathname + url.search + url.hash);
  }}
  closeButton.addEventListener("click", closeModal);
  backdrop.addEventListener("click", function(event) {{
    if (event.target === backdrop) closeModal();
  }});
  document.addEventListener("keydown", function(event) {{
    if (event.key === "Escape") closeModal();
  }});
  closeButton.focus();
}})();
</script>
"""


# ---------------- Configuration ----------------

DB_PATH = Path(os.getenv("MOTORGUARD_DB_PATH", "motorguard_users.db"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH")

MAX_LOGIN_ATTEMPTS = 5
ATTEMPT_WINDOW = 60
LOCKOUT_DURATION = 60

ph = PasswordHasher()
login_attempts = defaultdict(list)
locked_users = {}

logger = logging.getLogger("motorguard_security")
logger.setLevel(logging.INFO)
if not logger.handlers:
    file_handler = RotatingFileHandler(
        "security.log", maxBytes=1_000_000, backupCount=3
    )
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    ))
    logger.addHandler(file_handler)


# ---------------- Database ----------------

def db_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_auth_db():
    with db_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
                    CHECK(role IN ('admin', 'user')),
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'approved', 'rejected')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Preserve the existing .env administrator as the initial admin.
        if ADMIN_USERNAME and ADMIN_PASSWORD_HASH:
            db.execute("""
                INSERT OR IGNORE INTO users
                    (username, password_hash, role, status)
                VALUES (?, ?, 'admin', 'approved')
            """, (ADMIN_USERNAME, ADMIN_PASSWORD_HASH))


# ---------------- Helpers ----------------

def get_client_ip(request):
    # Do not trust X-Forwarded-For unless a trusted proxy is configured.
    return request.remote or "unknown"


def csrf_token(session):
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def csrf_is_valid(session, submitted):
    expected = session.get("csrf_token", "")
    return bool(expected and submitted and
                hmac.compare_digest(expected, submitted))


def page(content, title="MotorGuard"):
    return web.Response(
        text=f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;min-height:100vh;background:#080d16;
color:#eef2f8;font-family:Arial,sans-serif;display:flex;align-items:center;
justify-content:center;padding:22px}}
.card{{width:100%;max-width:440px;background:#111a28;border:1px solid #283449;
border-radius:18px;padding:32px;box-shadow:0 20px 60px #0007}}
.wide{{max-width:900px}} .brand{{color:#ff5555;font-size:25px;font-weight:800;
letter-spacing:1px;margin-bottom:8px}} .muted{{color:#9aa8bb;font-size:14px}}
h1{{font-size:23px;margin:24px 0 8px}} label{{display:block;margin:18px 0 8px;
font-size:13px;color:#cbd5e1}} input{{width:100%;padding:13px;background:#090f19;
border:1px solid #344258;border-radius:9px;color:white;outline:none}}
input:focus{{border-color:#ff5555}} button,.btn{{display:inline-block;
border:0;border-radius:9px;background:#ed4545;color:white;padding:12px 16px;
font-weight:700;cursor:pointer;text-decoration:none}} button[type=submit]{{width:100%;
margin-top:22px}} .secondary{{background:#263449}} .danger{{background:#8f3030}}
a{{color:#ff7777}} .message{{margin:14px 0;color:#ff9b9b;font-size:14px}}
.row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap}}
table{{width:100%;border-collapse:collapse;margin-top:20px;font-size:14px}}
td,th{{padding:12px;border-bottom:1px solid #29364a;text-align:left}}
.status{{color:#ffc66d}} .actions form{{display:inline}}
@media(max-width:520px){{.card{{padding:23px}}}}
</style>
</head>
<body>{content}</body></html>""",
        content_type="text/html"
    )


def form_message(request):
    return request.query.get("message", "")


# ---------------- Middleware ----------------

PUBLIC_PATHS = {
    "/login", "/signup", "/health", "/favicon.ico"
}

@web.middleware
async def auth_middleware(request, handler):
    if request.path in PUBLIC_PATHS or request.path.startswith("/static/"):
        return await handler(request)

    session = await get_session(request)
    if not session.get("authenticated"):
        if request.path == "/ws":
            return web.json_response(
                {"error": "Authentication required"}, status=401
            )
        raise web.HTTPFound("/login")

    if request.path.startswith("/admin"):
        if session.get("role") != "admin":
            raise web.HTTPForbidden(text="Administrator access required")

    return await handler(request)


# ---------------- Login / Signup ----------------

async def login_page(request):
    session = await get_session(request)
    token = csrf_token(session)

    error = request.query.get("error", "")
    popup_messages = {
        "invalid": ("Login failed", "Invalid username or password. Please try again."),
        "locked": ("Temporarily locked", "Too many failed attempts. Please wait 60 seconds before trying again."),
        "disabled": ("Account unavailable", "This account is disabled. Please contact the administrator.")
    }
    title, message = popup_messages.get(error, ("", ""))
    popup = MODAL_TEMPLATE.format(title=title, message=message) if message else ""

    content = f"""
<div class="card">
<div class="brand">MOTORGUARD<span style="color:white">.</span></div>
<div class="muted">INDUSTRIAL MONITORING SYSTEM</div>
<h1>Welcome back</h1>
<p class="muted">Sign in to access your monitoring dashboard.</p>
<form method="post" action="/login">
<input type="hidden" name="csrf_token" value="{token}">
<label>Username</label>
<input name="username" autocomplete="username" required maxlength="40">
<label>Password</label>
<input type="password" name="password" autocomplete="current-password" required>
<button type="submit">Sign in</button>
</form>
<p class="muted">New to MotorGuard? <a href="/signup">Create an account</a></p>
</div>{popup}"""
    return page(content, "MotorGuard | Login")


async def login_submit(request):
    session = await get_session(request)
    form = await request.post()

    if not csrf_is_valid(session, form.get("csrf_token", "")):
        raise web.HTTPForbidden(text="Invalid form token. Refresh and try again.")

    ip = get_client_ip(request)
    now = time.monotonic()
    locked_until = locked_users.get(ip, 0)

    if now < locked_until:
        logger.warning("Login blocked during lockout from %s", ip)
        raise web.HTTPSeeOther(location="/login?error=locked")

    attempts = [t for t in login_attempts[ip] if now - t < ATTEMPT_WINDOW]
    login_attempts[ip] = attempts

    username = form.get("username", "").strip()
    password = form.get("password", "")

    with db_connection() as db:
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

    valid = False
    if user:
        try:
            valid = ph.verify(user["password_hash"], password)
        except (VerifyMismatchError, VerificationError, Exception):
            valid = False

    if not valid:
        login_attempts[ip].append(now)
        if len(login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS:
            locked_users[ip] = now + LOCKOUT_DURATION
            login_attempts[ip].clear()
            logger.warning("Login lockout activated for %s", ip)
        logger.warning("Failed login attempt for username %s from %s", username, ip)
        raise web.HTTPSeeOther(location="/login?error=invalid")

    if user["status"] != "approved":
        raise web.HTTPSeeOther(location="/login?error=disabled")

    login_attempts.pop(ip, None)
    locked_users.pop(ip, None)

    session.clear()
    session["authenticated"] = True
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["user_id"] = user["id"]
    session["csrf_token"] = secrets.token_urlsafe(32)

    logger.info("Successful %s login for %s from %s", user["role"], user["username"], ip)
    raise web.HTTPFound("/")


async def signup_page(request):
    session = await get_session(request)
    token = csrf_token(session)

    error = request.query.get("error", "")
    popup_messages = {
        "exists": ("Username already exists", "This username is already registered. Please choose another username or sign in."),
        "password_mismatch": ("Passwords don't match", "The passwords do not match. Please enter the same password in both fields.")
    }
    title, message = popup_messages.get(error, ("", ""))
    popup = MODAL_TEMPLATE.format(title=title, message=message) if message else ""

    content = f"""
<div class="card">
<div class="brand">MOTORGUARD<span style="color:white">.</span></div>
<div class="muted">ACCOUNT REGISTRATION</div>
<h1>Create your account</h1>
<p class="muted">Create an account to access your MotorGuard dashboard.</p>
<form method="post" action="/signup">
<input type="hidden" name="csrf_token" value="{token}">
<label>Username</label>
<input name="username" autocomplete="username" required minlength="3" maxlength="40"
pattern="[A-Za-z0-9_.-]+" title="Use letters, numbers, dots, underscores or hyphens">
<label>Password</label>
<input type="password" name="password" autocomplete="new-password" required minlength="12">
<label>Confirm password</label>
<input type="password" name="confirm_password" autocomplete="new-password" required minlength="12">
<button type="submit">Create account</button>
</form>
<p class="muted">Already have an account? <a href="/login">Sign in</a></p>
</div>{popup}"""
    return page(content, "MotorGuard | Sign Up")


async def signup_submit(request):
    session = await get_session(request)
    form = await request.post()

    if not csrf_is_valid(session, form.get("csrf_token", "")):
        raise web.HTTPForbidden(text="Invalid form token. Refresh and try again.")

    username = form.get("username", "").strip()
    password = form.get("password", "")
    confirm = form.get("confirm_password", "")

    if len(username) < 3 or len(username) > 40:
        raise web.HTTPBadRequest(text="Username must be 3–40 characters.")
    if password != confirm:
        raise web.HTTPSeeOther(location="/signup?error=password_mismatch")
    if len(password) < 12:
        raise web.HTTPBadRequest(text="Password must be at least 12 characters.")

    password_hash = ph.hash(password)
    try:
        with db_connection() as db:
            db.execute("""
                INSERT INTO users (username, password_hash, role, status)
                VALUES (?, ?, 'user', 'approved')
            """, (username, password_hash))
    except sqlite3.IntegrityError:
        raise web.HTTPSeeOther(location="/signup?error=exists")

    logger.info("New user registration for %s from %s",
                username, get_client_ip(request))
    raise web.HTTPFound("/login?message=Account+created.+You+can+now+sign+in.")


# ---------------- Admin user management ----------------

async def admin_users(request):
    with db_connection() as db:
        users = db.execute("""
            SELECT id, username, role, status, created_at
            FROM users
            ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END, created_at
        """).fetchall()

    session = await get_session(request)
    token = csrf_token(session)
    current_user_id = session.get("user_id")

    rows = ""
    for user in users:
        username = html.escape(user["username"])
        if user["id"] == current_user_id:
            role_control = '<span class="muted">Your account</span>'
        else:
            selected_admin = "selected" if user["role"] == "admin" else ""
            selected_user = "selected" if user["role"] == "user" else ""
            role_control = f"""
            <form method="post" action="/admin/users/{user['id']}/role" class="row">
              <input type="hidden" name="csrf_token" value="{token}">
              <select name="role" aria-label="Role for {username}">
                <option value="user" {selected_user}>User</option>
                <option value="admin" {selected_admin}>Admin</option>
              </select>
              <button type="submit">Save role</button>
            </form>"""

        rows += f"""<tr>
<td>{username}</td>
<td>{user['role'].title()}</td>
<td class="status">{user['status'].title()}</td>
<td>{user['created_at']}</td>
<td class="actions">{role_control}</td>
</tr>"""

    if not rows:
        rows = '<tr><td colspan="5">No registered users yet.</td></tr>'

    content = f"""
<div class="card wide">
<div class="brand">MOTORGUARD<span style="color:white">.</span></div>
<h1>User management</h1>
<p class="muted">View registered accounts and manage their access roles.</p>
<p class="muted">Signed in as {html.escape(str(session.get('username', '')))} · Administrator</p>
<div class="row" style="margin-top:18px">
<a class="btn secondary" href="/">Dashboard</a>
<form method="post" action="/logout">
<input type="hidden" name="csrf_token" value="{token}">
<button class="danger">Logout</button></form>
</div>
<table><thead><tr><th>Username</th><th>Role</th><th>Status</th>
<th>Registered</th><th>Manage role</th></tr></thead><tbody>{rows}</tbody></table>
</div>
<style>
select{{background:#090f19;color:#eef2f8;border:1px solid #344258;
border-radius:8px;padding:10px}}
.actions form{{display:flex;gap:8px;align-items:center}}
@media(max-width:700px){{.card.wide{{overflow-x:auto}} table{{min-width:680px}}}}
</style>"""
    return page(content, "MotorGuard | User Management")


async def update_user_status(request):
    session = await get_session(request)
    form = await request.post()
    if not csrf_is_valid(session, form.get("csrf_token", "")):
        raise web.HTTPForbidden(text="Invalid form token.")

    user_id = int(request.match_info["user_id"])
    new_status = request.match_info["status"]

    if new_status not in {"approved", "rejected"}:
        raise web.HTTPBadRequest(text="Invalid status.")

    with db_connection() as db:
        target = db.execute(
            "SELECT id, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not target:
            raise web.HTTPNotFound(text="User not found.")
        if target["role"] == "admin":
            raise web.HTTPForbidden(text="Admin accounts cannot be changed here.")
        db.execute("UPDATE users SET status = ? WHERE id = ?",
                   (new_status, user_id))

    logger.info("Admin %s set user id %s to %s",
                session.get("username"), user_id, new_status)
    raise web.HTTPSeeOther(location="/admin/users")


async def update_user_role(request):
    session = await get_session(request)
    form = await request.post()

    if not csrf_is_valid(session, form.get("csrf_token", "")):
        raise web.HTTPForbidden(text="Invalid form token.")

    try:
        user_id = int(request.match_info["user_id"])
    except (TypeError, ValueError):
        raise web.HTTPBadRequest(text="Invalid user ID.")

    new_role = form.get("role", "")
    if new_role not in {"admin", "user"}:
        raise web.HTTPBadRequest(text="Invalid role.")

    if user_id == session.get("user_id"):
        raise web.HTTPForbidden(text="You cannot change your own role.")

    with db_connection() as db:
        target = db.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not target:
            raise web.HTTPNotFound(text="User not found.")

        if target["role"] == "admin" and new_role == "user":
            admin_count = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin'"
            ).fetchone()[0]
            if admin_count <= 1:
                raise web.HTTPForbidden(
                    text="You cannot remove the last administrator."
                )

        db.execute(
            "UPDATE users SET role = ?, status = 'approved' WHERE id = ?",
            (new_role, user_id)
        )

    logger.info(
        "Admin %s changed role for user id %s to %s",
        session.get("username"), user_id, new_role
    )
    raise web.HTTPSeeOther(location="/admin/users")


# ---------------- Logout ----------------

async def logout(request):
    session = await get_session(request)
    form = await request.post()
    if not csrf_is_valid(session, form.get("csrf_token", "")):
        raise web.HTTPForbidden(text="Invalid form token.")
    session.invalidate()
    raise web.HTTPSeeOther(location="/login")


# ---------------- Route registration ----------------

def register_auth_routes(app):
    init_auth_db()
    app.router.add_get("/login", login_page)
    app.router.add_post("/login", login_submit)
    app.router.add_get("/signup", signup_page)
    app.router.add_post("/signup", signup_submit)
    app.router.add_get("/admin/users", admin_users)
    app.router.add_post("/admin/users/{user_id}/role", update_user_role)
    app.router.add_post(
        "/admin/users/{user_id}/approve",
        lambda request: update_user_status_with_status(request, "approved")
    )
    app.router.add_post(
        "/admin/users/{user_id}/reject",
        lambda request: update_user_status_with_status(request, "rejected")
    )
    app.router.add_post("/logout", logout)


async def update_user_status_with_status(request, status):
    # Route wrapper passes a fixed status rather than accepting it from the URL.
    request.match_info  # keep request object untouched
    session = await get_session(request)
    form = await request.post()
    if not csrf_is_valid(session, form.get("csrf_token", "")):
        raise web.HTTPForbidden(text="Invalid form token.")

    user_id = int(request.match_info["user_id"])
    with db_connection() as db:
        target = db.execute(
            "SELECT id, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not target:
            raise web.HTTPNotFound(text="User not found.")
        if target["role"] == "admin":
            raise web.HTTPForbidden(text="Admin accounts cannot be changed here.")
        db.execute("UPDATE users SET status = ? WHERE id = ?",
                   (status, user_id))

    logger.info("Admin %s set user id %s to %s",
                session.get("username"), user_id, status)
    raise web.HTTPSeeOther(location="/admin/users")
