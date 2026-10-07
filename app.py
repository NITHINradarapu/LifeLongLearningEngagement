import re
import os
import json
import sqlite3
import secrets
from datetime import datetime, date, timedelta
from functools import wraps

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "learninglearning.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "dev-only-change-this-secret-key"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
app.config["DATABASE"] = DB_PATH

# Gemini is optional at import/startup time. The AI features provide a clear setup error if the SDK/key is missing.
try:
    from google import genai
    from pydantic import BaseModel, Field
    GEMINI_SDK_AVAILABLE = True
except Exception:
    genai = None
    BaseModel = object
    Field = lambda *a, **k: None
    GEMINI_SDK_AVAILABLE = False

# Read model from the environment; fall back to a known-good public alias.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or os.environ.get("GOOGLE_GENAI_MODEL") or "gemini-2.0-flash"

if GEMINI_SDK_AVAILABLE:
    class AIQuestion(BaseModel):
        question: str
        option_a: str
        option_b: str
        option_c: str
        option_d: str
        correct_answer: str = Field(description="One of A, B, C, D")
        explanation: str
        difficulty: str
        topic: str
        learning_objective: str

    class AIQuiz(BaseModel):
        title: str
        instructions: str
        questions: list[AIQuestion]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('student','admin')),
        skill_level TEXT NOT NULL DEFAULT 'beginner',
        career_goal TEXT DEFAULT '',
        streak INTEGER NOT NULL DEFAULT 0,
        last_active TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT DEFAULT 'General',
        level TEXT NOT NULL DEFAULT 'beginner',
        career_target TEXT DEFAULT '',
        video_url TEXT DEFAULT '',
        published INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        enrolled_at TEXT NOT NULL,
        progress REAL NOT NULL DEFAULT 0,
        completed INTEGER NOT NULL DEFAULT 0,
        last_watched REAL NOT NULL DEFAULT 0,
        UNIQUE(student_id, course_id),
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        timestamp_seconds REAL NOT NULL,
        question TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_option TEXT NOT NULL,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS checkpoint_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        checkpoint_id INTEGER NOT NULL,
        correct INTEGER NOT NULL,
        attempted_at TEXT NOT NULL,
        UNIQUE(student_id, checkpoint_id),
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(checkpoint_id) REFERENCES checkpoints(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        score REAL NOT NULL,
        completion_seconds REAL NOT NULL DEFAULT 0,
        taken_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        attendance_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'present',
        UNIQUE(student_id, course_id, attendance_date),
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        instructions TEXT DEFAULT '',
        difficulty TEXT NOT NULL DEFAULT 'adaptive',
        question_count INTEGER NOT NULL DEFAULT 10,
        generated_by TEXT NOT NULL DEFAULT 'gemini',
        status TEXT NOT NULL DEFAULT 'published',
        created_at TEXT NOT NULL,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS assessment_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_answer TEXT NOT NULL,
        explanation TEXT DEFAULT '',
        difficulty TEXT DEFAULT 'intermediate',
        topic TEXT DEFAULT '',
        learning_objective TEXT DEFAULT '',
        FOREIGN KEY(assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS assessment_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        student_id INTEGER NOT NULL,
        score REAL NOT NULL,
        correct_answers INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        completion_seconds REAL NOT NULL DEFAULT 0,
        started_at TEXT,
        completed_at TEXT NOT NULL,
        FOREIGN KEY(assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS assessment_answers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        selected_answer TEXT NOT NULL,
        is_correct INTEGER NOT NULL,
        FOREIGN KEY(attempt_id) REFERENCES assessment_attempts(id) ON DELETE CASCADE,
        FOREIGN KEY(question_id) REFERENCES assessment_questions(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS learner_topic_performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        topic TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        correct_answers INTEGER NOT NULL DEFAULT 0,
        accuracy REAL NOT NULL DEFAULT 0,
        strength_level TEXT NOT NULL DEFAULT 'developing',
        last_updated TEXT NOT NULL,
        UNIQUE(student_id, course_id, topic),
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        notification_type TEXT NOT NULL DEFAULT 'info',
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_notifications_recipient
        ON notifications(recipient_id, is_read, created_at);
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        recipient_id INTEGER NOT NULL,
        subject TEXT NOT NULL DEFAULT 'Student Query',
        message TEXT NOT NULL,
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_messages_recipient ON messages(recipient_id, is_read, created_at);

    CREATE TABLE IF NOT EXISTS learning_path_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        course_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 50,
        status TEXT NOT NULL DEFAULT 'recommended',
        created_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
        UNIQUE(student_id, course_id)
    );

    CREATE TABLE IF NOT EXISTS daily_learning_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        goal_date TEXT NOT NULL,
        target_minutes INTEGER NOT NULL DEFAULT 30,
        completed_minutes INTEGER NOT NULL DEFAULT 0,
        target_checkpoints INTEGER NOT NULL DEFAULT 1,
        completed_checkpoints INTEGER NOT NULL DEFAULT 0,
        UNIQUE(student_id, goal_date),
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS gamification_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        points INTEGER NOT NULL DEFAULT 0,
        description TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ai_generation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        student_id INTEGER,
        course_id INTEGER,
        model TEXT NOT NULL,
        question_count INTEGER NOT NULL,
        prompt_context TEXT,
        status TEXT NOT NULL,
        error_message TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(admin_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE SET NULL
    );
    """)

    # Existing databases from earlier versions may not have created_at.
    cols = {r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()}
    if "created_at" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
        db.execute("UPDATE users SET created_at=? WHERE created_at IS NULL", (datetime.now().isoformat(),))

    # Create the first administrator from environment variables. No demo student is created.
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@adaptivelearn.local").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "ChangeMe@123!")
    admin_name = os.environ.get("ADMIN_NAME", "Platform Administrator")
    if not db.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone():
        db.execute("""INSERT INTO users(name,email,password_hash,role,skill_level,career_goal,created_at)
                      VALUES(?,?,?,?,?,?,?)""", (admin_name, admin_email, generate_password_hash(admin_password),
                      "admin", "advanced", "Learning Platform Administration", datetime.now().isoformat()))
    # Lightweight migrations for databases created by earlier versions.
    existing_tables = {r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "notifications" not in existing_tables:
        db.execute("""CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'info',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
    if "learning_path_items" not in existing_tables:
        db.execute("""CREATE TABLE learning_path_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 50,
            status TEXT NOT NULL DEFAULT 'recommended',
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(student_id,course_id)
        )""")
    if "daily_learning_goals" not in existing_tables:
        db.execute("""CREATE TABLE daily_learning_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            goal_date TEXT NOT NULL,
            target_minutes INTEGER NOT NULL DEFAULT 30,
            completed_minutes INTEGER NOT NULL DEFAULT 0,
            target_checkpoints INTEGER NOT NULL DEFAULT 1,
            completed_checkpoints INTEGER NOT NULL DEFAULT 0,
            UNIQUE(student_id,goal_date),
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
    if "gamification_events" not in existing_tables:
        db.execute("""CREATE TABLE gamification_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            points INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
    db.commit()


def ensure_database():
    if not os.path.exists(DB_PATH):
        os.makedirs(BASE_DIR, exist_ok=True)
        with app.app_context():
            init_db()


@app.before_request
def startup_database():
    ensure_database()


# ---------------------------------------------------------------------------
# CSRF protection
# ---------------------------------------------------------------------------

CSRF_EXEMPT_ENDPOINTS = {"login", "register", "static"}


def _csrf_token() -> str:
    """Return (creating if needed) a per-session CSRF token."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


@app.before_request
def csrf_protect():
    """Reject mutating requests that do not carry a valid CSRF token."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    if request.endpoint in CSRF_EXEMPT_ENDPOINTS:
        return
    # JSON API endpoints receive the token in a custom header.
    if request.is_json:
        token = request.headers.get("X-CSRF-Token", "")
    else:
        token = request.form.get("_csrf_token", "")
    expected = session.get("_csrf_token", "")
    if not expected or not secrets.compare_digest(token, expected):
        abort(403, description="CSRF token missing or invalid.")


@app.context_processor
def inject_csrf_token():
    """Make csrf_token() available to every template automatically."""
    return {"csrf_token": _csrf_token}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        # A session can outlive a deleted/reset database user. Always verify
        # that the user still exists before allowing a protected view to run.
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = current_user()
        if user is None:
            flash("Your session is no longer valid. Please sign in again.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("role") != role:
                flash("You are not authorized to access that page.", "danger")
                return redirect(url_for("index"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def current_user():
    if "user_id" not in session:
        return None
    user = get_db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if user is None:
        session.clear()
    return user


@app.context_processor
def inject_globals():
    return {"current_user": current_user()}


def update_streak(user_id):
    db = get_db()
    row = db.execute("SELECT streak,last_active FROM users WHERE id=?", (user_id,)).fetchone()
    # A stale session can point to a deleted user. Never subscript a missing row.
    if row is None:
        session.clear()
        return 0
    today = date.today()
    last = None
    if row["last_active"]:
        try:
            last = date.fromisoformat(row["last_active"])
        except ValueError:
            pass
    streak = row["streak"] or 0
    if last == today:
        return streak
    streak = streak + 1 if last == today - timedelta(days=1) else 1
    db.execute("UPDATE users SET streak=?,last_active=? WHERE id=?", (streak, today.isoformat(), user_id))
    db.commit()
    return streak


def calculate_level(score):
    if score >= 80:
        return "advanced"
    if score >= 50:
        return "intermediate"
    return "beginner"


def get_adaptive_context(student_id, course_id):
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id=? AND role='student'", (student_id,)).fetchone()
    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    if student is None:
        raise ValueError("The selected learner no longer exists. Please choose another learner.")
    if course is None:
        raise ValueError("The selected course no longer exists.")
    history = db.execute("""SELECT score, completion_seconds, taken_at FROM quiz_results
                           WHERE student_id=? AND course_id=? ORDER BY taken_at DESC LIMIT 8""", (student_id, course_id)).fetchall()
    topics = db.execute("""SELECT topic, attempts, accuracy, strength_level FROM learner_topic_performance
                          WHERE student_id=? AND course_id=? ORDER BY accuracy ASC""", (student_id, course_id)).fetchall()
    return student, course, history, topics


def generate_ai_quiz(student_id, course_id, count=10, difficulty="adaptive", admin_id=None):
    if not GEMINI_SDK_AVAILABLE:
        raise RuntimeError("Google GenAI SDK is not installed. Run: pip install -r requirements.txt")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if not api_key:
        raise RuntimeError("Gemini API key is not configured. Set GEMINI_API_KEY in your environment.")

    db = get_db()
    if student_id:
        student, course, history, topics = get_adaptive_context(student_id, course_id)
    else:
        course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        if course is None:
            raise ValueError("The selected course no longer exists.")
        student = {"skill_level": course["level"] or "beginner", "career_goal": course["career_target"] or "Not specified"}
        history, topics = [], []
    weak_topics = [f"{t['topic']} ({t['accuracy']:.0f}% accuracy)" for t in topics if t["accuracy"] < 70][:6]
    strong_topics = [f"{t['topic']} ({t['accuracy']:.0f}% accuracy)" for t in topics if t["accuracy"] >= 70][:6]
    history_text = "; ".join(f"{h['score']:.0f}%" for h in history) or "No previous assessments"

    prompt = f"""
You are the assessment engine for an adaptive lifelong learning platform.
Generate exactly {max(5, min(int(count), 30))} high-quality multiple-choice questions.
Course: {course['title']}
Category: {course['category']}
Course level: {course['level']}
Course description: {course['description']}
Career target: {course['career_target']}
Learner level: {student['skill_level']}
Learner career goal: {student['career_goal'] or 'Not specified'}
Previous scores: {history_text}
Weak topics to remediate: {', '.join(weak_topics) or 'Not established'}
Strong topics to extend: {', '.join(strong_topics) or 'Not established'}
Requested difficulty: {difficulty}

Rules:
- Cover the course description and career target.
- Adapt difficulty to the learner; use more remediation questions for weak topics and a smaller number of stretch questions for strong topics.
- Every question must have exactly four plausible options and exactly one correct answer.
- Do not use trick wording, ambiguous answers, or duplicate questions.
- Include a concise explanation and a measurable learning objective for every question.
- Use difficulty values beginner, intermediate, or advanced.
- Return only the requested structured JSON object.
"""

    log_id = None
    try:
        cur = db.execute("""INSERT INTO ai_generation_logs(admin_id,student_id,course_id,model,question_count,prompt_context,status,created_at)
                            VALUES(?,?,?,?,?,?,?,?)""", (admin_id, student_id, course_id, GEMINI_MODEL, count, prompt[:4000], "started", datetime.now().isoformat()))
        log_id = cur.lastrowid
        db.commit()
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json", "response_schema": AIQuiz},
        )
        quiz = response.parsed if getattr(response, "parsed", None) else AIQuiz.model_validate_json(response.text)
        if len(quiz.questions) < 5:
            raise RuntimeError("Gemini returned too few questions. Please regenerate the assessment.")
        if len(quiz.questions) > 30:
            quiz.questions = quiz.questions[:30]
        if log_id:
            db.execute("UPDATE ai_generation_logs SET status='success' WHERE id=?", (log_id,))
            db.commit()
        return quiz
    except Exception as exc:
        if log_id:
            db.execute("UPDATE ai_generation_logs SET status='failed',error_message=? WHERE id=?", (str(exc)[:1000], log_id))
            db.commit()
        raise


def save_assessment(course_id, quiz, difficulty="adaptive"):
    db = get_db()
    cur = db.execute("""INSERT INTO assessments(course_id,title,instructions,difficulty,question_count,generated_by,status,created_at)
                       VALUES(?,?,?,?,?,'gemini','published',?)""",
                     (course_id, quiz.title, quiz.instructions, difficulty, len(quiz.questions), datetime.now().isoformat()))
    assessment_id = cur.lastrowid
    for q in quiz.questions:
        answer = str(q.correct_answer).strip().upper()
        if answer not in {"A", "B", "C", "D"}:
            answer = "A"
        db.execute("""INSERT INTO assessment_questions(assessment_id,question,option_a,option_b,option_c,option_d,
                    correct_answer,explanation,difficulty,topic,learning_objective)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (assessment_id, q.question, q.option_a, q.option_b, q.option_c,
                    q.option_d, answer, q.explanation, q.difficulty, q.topic, q.learning_objective))
    db.commit()
    return assessment_id


@app.route("/")
def index():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    if session.get("role") == "student":
        return redirect(url_for("student_dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    form = {"name": "", "email": "", "career_goal": ""}
    if request.method == "POST":
        form["name"] = request.form.get("name", "").strip()
        form["email"] = request.form.get("email", "").strip().lower()
        form["career_goal"] = request.form.get("career_goal", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(form["name"]) < 2:
            flash("Please enter your full name.", "danger")
            return render_template("register.html", form=form)
        if "@" not in form["email"] or "." not in form["email"].rsplit("@", 1)[-1]:
            flash("Please enter a valid email address.", "danger")
            return render_template("register.html", form=form)
        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return render_template("register.html", form=form)
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", form=form)

        try:
            db = get_db()
            db.execute(
                """INSERT INTO users(name,email,password_hash,role,career_goal,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (form["name"], form["email"], generate_password_hash(password),
                 "student", form["career_goal"], datetime.now().isoformat())
            )
            db.commit()
            flash("Account created successfully. Sign in to begin your personalized learning path.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered. Please sign in or use another email.", "danger")
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = {"email": ""}
    if request.method == "POST":
        form["email"] = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not form["email"] or not password:
            flash("Enter your email and password.", "danger")
            return render_template("login.html", form=form)

        user = get_db().execute("SELECT * FROM users WHERE email=?", (form["email"],)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            update_streak(user["id"])
            return redirect(url_for("index"))
        flash("Invalid email or password. Please check your credentials and try again.", "danger")
    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def get_student_achievements(student_id, user=None):
    """Return live achievement status and progress for the student dashboard."""
    db = get_db()
    user = user or db.execute("SELECT * FROM users WHERE id=?", (student_id,)).fetchone()
    checkpoint_count = db.execute(
        "SELECT COUNT(*) AS n FROM checkpoint_attempts WHERE student_id=? AND correct=1",
        (student_id,)
    ).fetchone()["n"]
    assessment_count = db.execute(
        "SELECT COUNT(*) AS n FROM assessment_attempts WHERE student_id=?", (student_id,)
    ).fetchone()["n"]
    topic_count = db.execute(
        "SELECT COUNT(*) AS n FROM learner_topic_performance WHERE student_id=?", (student_id,)
    ).fetchone()["n"]
    completed_courses = db.execute(
        "SELECT COUNT(*) AS n FROM enrollments WHERE student_id=? AND completed=1", (student_id,)
    ).fetchone()["n"]

    streak = int(user["streak"] or 0)
    skill = (user["skill_level"] or "beginner").lower()
    analytics_ready = (assessment_count + topic_count + completed_courses) > 0

    return [
        {"key":"streak_builder", "icon":"bi-fire", "title":"Streak Builder",
         "description":"Maintain a daily learning habit", "unlocked":streak >= 3,
         "progress":min(streak,3), "target":3, "progress_text":f"{min(streak,3)}/3 learning days"},
        {"key":"fast_learner", "icon":"bi-lightning-charge-fill", "title":"Fast Learner",
         "description":"Complete checkpoints actively", "unlocked":checkpoint_count >= 3,
         "progress":min(checkpoint_count,3), "target":3, "progress_text":f"{min(checkpoint_count,3)}/3 checkpoints"},
        {"key":"progress_tracker", "icon":"bi-bar-chart-fill", "title":"Progress Tracker",
         "description":"Monitor your learning analytics", "unlocked":analytics_ready,
         "progress":1 if analytics_ready else 0, "target":1,
         "progress_text":"Analytics data available" if analytics_ready else "Complete a learning activity"},
        {"key":"skill_growth", "icon":"bi-award-fill", "title":"Skill Growth",
         "description":"Advance your learning level", "unlocked":skill in {"intermediate","advanced"},
         "progress":2 if skill == "advanced" else 1 if skill == "intermediate" else 0, "target":2,
         "progress_text":"Advanced level" if skill == "advanced" else "Intermediate level" if skill == "intermediate" else "Beginner → Intermediate"}
    ]



def create_notification(recipient_id, title, message, notification_type="info"):
    """Create an in-app notification for a student or admin."""
    db = get_db()
    db.execute(
        """INSERT INTO notifications(recipient_id,title,message,notification_type,is_read,created_at)
           VALUES(?,?,?,?,0,?)""",
        (recipient_id, title, message, notification_type, datetime.now().isoformat())
    )
    db.commit()


def create_broadcast_notification(sender_id, title, message, notification_type="announcement"):
    """Send an in-app notification to every user except the sender."""
    db = get_db()
    rows = db.execute("SELECT id FROM users WHERE id<>?", (sender_id,)).fetchall()
    now = datetime.now().isoformat()
    db.executemany(
        """INSERT INTO notifications(recipient_id,title,message,notification_type,is_read,created_at)
           VALUES(?,?,?,?,0,?)""",
        [(r["id"], title, message, notification_type, 0, now) for r in rows]
    )
    db.commit()
    return len(rows)


def get_notifications(user_id, limit=8):
    db = get_db()
    return db.execute(
        """SELECT * FROM notifications
           WHERE recipient_id=?
           ORDER BY is_read ASC, created_at DESC
           LIMIT ?""",
        (user_id, limit)
    ).fetchall()


def get_notification_count(user_id):
    return get_db().execute(
        "SELECT COUNT(*) AS n FROM notifications WHERE recipient_id=? AND is_read=0",
        (user_id,)
    ).fetchone()["n"]


@app.route("/api/notifications")
@login_required
def api_notifications():
    user_id=session["user_id"]
    rows=get_notifications(user_id, 8)
    return jsonify({
        "unread": get_notification_count(user_id),
        "notifications": [dict(r) for r in rows]
    })


def sync_daily_goal(student_id):
    """Create today's adaptive micro-goal and update its checkpoint count."""
    db = get_db()
    today = date.today().isoformat()
    db.execute(
        """INSERT OR IGNORE INTO daily_learning_goals
           (student_id,goal_date,target_minutes,completed_minutes,target_checkpoints,completed_checkpoints)
           VALUES(?,?,30,0,1,0)""",
        (student_id, today)
    )
    cp = db.execute(
        """SELECT COUNT(*) AS n
           FROM checkpoint_attempts ca JOIN checkpoints c ON c.id=ca.checkpoint_id
           WHERE ca.student_id=? AND ca.correct=1 AND date(ca.attempted_at)=?""",
        (student_id, today)
    ).fetchone()["n"]
    db.execute(
        "UPDATE daily_learning_goals SET completed_checkpoints=? WHERE student_id=? AND goal_date=?",
        (cp, student_id, today)
    )
    db.commit()
    return db.execute(
        "SELECT * FROM daily_learning_goals WHERE student_id=? AND goal_date=?",
        (student_id, today)
    ).fetchone()


def build_personalized_recommendations(student_id, limit=6):
    """
    Recommendation engine:
    - excludes enrolled courses
    - prioritizes learner level
    - matches career goal/category
    - prioritizes weak topics/categories
    - gives a small freshness bonus
    """
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id=?", (student_id,)).fetchone()
    if not student:
        return []

    enrolled = {r["course_id"] for r in db.execute(
        "SELECT course_id FROM enrollments WHERE student_id=?", (student_id,)
    ).fetchall()}

    weak = db.execute(
        """SELECT topic, accuracy FROM learner_topic_performance
           WHERE student_id=? ORDER BY accuracy ASC LIMIT 5""",
        (student_id,)
    ).fetchall()
    weak_terms = [(r["topic"] or "").lower() for r in weak if r["accuracy"] < 70]
    career = (student["career_goal"] or "").lower()
    level = (student["skill_level"] or "beginner").lower()

    courses = db.execute(
        "SELECT * FROM courses WHERE published=1 ORDER BY id DESC"
    ).fetchall()

    ranked = []
    for c in courses:
        if c["id"] in enrolled:
            continue
        score = 0
        reasons = []

        clevel = (c["level"] or "").lower()
        text = " ".join([
            c["title"] or "", c["description"] or "", c["category"] or "",
            c["career_target"] or ""
        ]).lower()

        if clevel == level:
            score += 45
            reasons.append("matches your current level")
        elif (level == "beginner" and clevel == "intermediate") or (level == "intermediate" and clevel == "advanced"):
            score += 22
            reasons.append("supports your next skill level")

        if career and any(term.strip() and term.strip() in text for term in re.split(r"[,;/ ]+", career)):
            score += 35
            reasons.append("aligned with your career goal")

        weak_hits = [t for t in weak_terms if t and t in text]
        if weak_hits:
            score += 35
            reasons.append("strengthens a topic that needs focus")

        if c["category"] and any(k in text for k in ["project", "practice", "hands-on"]):
            score += 4
        score += min(int(c["id"]), 20) * 0.1

        reason = "; ".join(reasons[:2]) or "a useful next step in your learning journey"
        ranked.append((score, c, reason))

    ranked.sort(key=lambda x: x[0], reverse=True)
    selected = ranked[:limit]

    # Persist the current path without deleting learner history.
    now = datetime.now().isoformat()
    for priority, (_, c, reason) in enumerate(selected, 1):
        db.execute(
            """INSERT INTO learning_path_items(student_id,course_id,reason,priority,status,created_at)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(student_id,course_id) DO UPDATE SET
               reason=excluded.reason, priority=excluded.priority, status='recommended',
               created_at=excluded.created_at""",
            (student_id, c["id"], reason, priority, "recommended", now)
        )
    db.commit()
    return [
        dict(c, recommendation_reason=reason, recommendation_priority=i)
        for i, (_, c, reason) in enumerate(selected, 1)
    ]


def award_points(student_id, points, event_type, description):
    db = get_db()
    db.execute(
        "INSERT INTO gamification_events(student_id,event_type,points,description,created_at) VALUES(?,?,?,?,?)",
        (student_id, event_type, points, description, datetime.now().isoformat())
    )
    db.commit()


def get_gamification_summary(student_id):
    db = get_db()
    total = db.execute(
        "SELECT COALESCE(SUM(points),0) AS n FROM gamification_events WHERE student_id=?",
        (student_id,)
    ).fetchone()["n"]
    return {
        "points": int(total),
        "level": 1 + int(total // 100),
        "next_level": int(((total // 100) + 1) * 100),
        "progress": int(total % 100)
    }


@app.context_processor
def inject_notification_globals():
    user = current_user()
    if not user:
        return {"notifications": [], "notification_count": 0}
    return {
        "notifications": get_notifications(user["id"], 8),
        "notification_count": get_notification_count(user["id"])
    }


@app.route("/notifications/read/<int:notification_id>", methods=["POST"])
@login_required
def notification_read(notification_id):
    db = get_db()
    db.execute(
        "UPDATE notifications SET is_read=1 WHERE id=? AND recipient_id=?",
        (notification_id, session["user_id"])
    )
    db.commit()
    return jsonify({"ok": True, "unread": get_notification_count(session["user_id"])})


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def notifications_read_all():
    db = get_db()
    db.execute("UPDATE notifications SET is_read=1 WHERE recipient_id=?", (session["user_id"],))
    db.commit()
    return jsonify({"ok": True})


@app.route("/notifications/send", methods=["POST"])
@login_required
@role_required("admin")
def admin_send_notification():
    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    target = (request.form.get("target", "students") or "students").strip().lower()
    kind = request.form.get("notification_type", "announcement")
    if not title or not message:
        flash("Notification title and message are required.", "danger")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    if target in {"all", "everyone_except_me", "everyone except me", "except_me"}:
        # Explicitly exclude the sender and deliver to every other account.
        rows = db.execute("SELECT id FROM users WHERE id <> ?", (session["user_id"],)).fetchall()
    else:
        # All students means students only, never other administrators.
        rows = db.execute("SELECT id FROM users WHERE role='student'").fetchall()

    now = datetime.now().isoformat()
    db.executemany(
        """INSERT INTO notifications(recipient_id,title,message,notification_type,is_read,created_at)
           VALUES(?,?,?,?,0,?)""",
        [(r["id"], title, message, kind, now) for r in rows]
    )
    db.commit()
    flash(f"Notification sent to {len(rows)} user(s).", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/notifications/clear", methods=["POST"])
@login_required
@role_required("admin")
def admin_notifications_clear():
    db = get_db()
    db.execute(
        """DELETE FROM notifications
           WHERE recipient_id=? AND is_read=1""",
        (session["user_id"],)
    )
    db.commit()
    flash("Read notifications cleared.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/student/learning-path")
@login_required
@role_required("student")
def student_learning_path():
    student_id = session["user_id"]
    goal = sync_daily_goal(student_id)
    recommendations = build_personalized_recommendations(student_id, 12)
    return render_template(
        "learning_path.html",
        user=current_user(), goal=goal, recommendations=recommendations,
        gamification=get_gamification_summary(student_id)
    )



@app.route("/student/dashboard")
@login_required
@role_required("student")
def student_dashboard():
    db = get_db(); user = current_user()
    enrollments = db.execute("""SELECT e.*,c.title,c.category,c.level,c.description,c.video_url
        FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=? ORDER BY e.enrolled_at DESC""", (user["id"],)).fetchall()
    recommendations = build_personalized_recommendations(user["id"], 6)
    goal = sync_daily_goal(user["id"])
    gamification = get_gamification_summary(user["id"])
    weak_topics = db.execute(
        """SELECT topic,accuracy,strength_level FROM learner_topic_performance
           WHERE student_id=? ORDER BY accuracy ASC LIMIT 4""",
        (user["id"],)
    ).fetchall()
    stats = db.execute("""SELECT
        (SELECT COUNT(*) FROM enrollments WHERE student_id=?) enrolled,
        (SELECT COUNT(*) FROM enrollments WHERE student_id=? AND completed=1) completed,
        (SELECT COALESCE(AVG(score),0) FROM assessment_attempts WHERE student_id=?) avg_score,
        (SELECT COUNT(*) FROM attendance WHERE student_id=? AND status='present') attendance_count,
        (SELECT COUNT(*) FROM assessment_attempts WHERE student_id=?) assessments""",
        (user["id"], user["id"], user["id"], user["id"], user["id"])).fetchone()
    achievements = get_student_achievements(user["id"], user)
    unlocked_achievements = sum(1 for a in achievements if a["unlocked"])
    return render_template("student_dashboard.html", user=user, enrollments=enrollments,
                           recommendations=recommendations, stats=stats, goal=goal,
                           gamification=gamification, weak_topics=weak_topics,
                           achievements=achievements, unlocked_achievements=unlocked_achievements)

@app.route("/analytics")
@login_required
@role_required("student")
def analytics():
    """Personal learning analytics for the authenticated student."""
    db = get_db()
    student_id = session["user_id"]
    results = db.execute("""
        SELECT qr.score, qr.completion_seconds, qr.taken_at, c.title AS course_title
        FROM quiz_results qr
        JOIN courses c ON c.id = qr.course_id
        WHERE qr.student_id = ?
        ORDER BY qr.taken_at DESC
        LIMIT 20
    """, (student_id,)).fetchall()
    attendance = db.execute("""
        SELECT a.attendance_date, a.status, c.title
        FROM attendance a
        JOIN courses c ON c.id = a.course_id
        WHERE a.student_id = ?
        ORDER BY a.attendance_date DESC
        LIMIT 50
    """, (student_id,)).fetchall()
    topics = db.execute("""
        SELECT topic, accuracy, strength_level
        FROM learner_topic_performance
        WHERE student_id = ?
        ORDER BY accuracy ASC
    """, (student_id,)).fetchall()
    return render_template("analytics.html", user=current_user(), results=results, attendance=attendance, topics=topics)


@app.route("/courses")
@login_required
@role_required("student")
def course_catalog():
    courses = get_db().execute("SELECT * FROM courses WHERE published=1 ORDER BY id DESC").fetchall()
    return render_template("courses.html", courses=courses)


@app.route("/student/enroll/<int:course_id>", methods=["POST"])
@login_required
@role_required("student")
def enroll(course_id):
    db = get_db(); course = db.execute("SELECT * FROM courses WHERE id=? AND published=1", (course_id,)).fetchone()
    if not course:
        flash("Course not available.", "danger"); return redirect(url_for("course_catalog"))
    try:
        db.execute("INSERT INTO enrollments(student_id,course_id,enrolled_at) VALUES(?,?,?)", (session["user_id"], course_id, datetime.now().isoformat()))
        db.commit(); update_streak(session["user_id"]); flash("Course added to your learning plan.", "success")
    except sqlite3.IntegrityError:
        flash("You are already enrolled in this course.", "info")
    return redirect(url_for("student_dashboard"))


@app.route("/student/course/<int:course_id>")
@login_required
@role_required("student")
def learn_course(course_id):
    db = get_db()
    enrollment = db.execute("SELECT e.*,c.* FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=? AND e.course_id=?", (session["user_id"], course_id)).fetchone()
    if not enrollment:
        flash("Enroll in this course first.", "warning"); return redirect(url_for("course_catalog"))
    checkpoints = db.execute("SELECT * FROM checkpoints WHERE course_id=? ORDER BY timestamp_seconds", (course_id,)).fetchall()
    attempts = db.execute("""SELECT ca.*,cp.timestamp_seconds FROM checkpoint_attempts ca JOIN checkpoints cp ON cp.id=ca.checkpoint_id
                            WHERE ca.student_id=? AND cp.course_id=?""", (session["user_id"], course_id)).fetchall()
    assessments = db.execute("SELECT * FROM assessments WHERE course_id=? AND status='published' ORDER BY created_at DESC", (course_id,)).fetchall()
    return render_template("learn.html", course=enrollment, checkpoints=checkpoints, attempts=attempts, assessments=assessments)


@app.route("/api/checkpoint", methods=["POST"])
@login_required
@role_required("student")
def checkpoint():
    data = request.get_json(silent=True) or {}; checkpoint_id = data.get("checkpoint_id"); answer = str(data.get("answer", "")).upper()
    db = get_db(); cp = db.execute("SELECT * FROM checkpoints WHERE id=?", (checkpoint_id,)).fetchone()
    if not cp: return jsonify({"ok": False, "message": "Checkpoint not found."}), 404
    existing = db.execute("SELECT * FROM checkpoint_attempts WHERE student_id=? AND checkpoint_id=?", (session["user_id"], checkpoint_id)).fetchone()
    correct = answer == cp["correct_option"].upper()
    if existing: correct = bool(existing["correct"])
    else: db.execute("INSERT INTO checkpoint_attempts(student_id,checkpoint_id,correct,attempted_at) VALUES(?,?,?,?)", (session["user_id"], checkpoint_id, int(correct), datetime.now().isoformat()))
    if correct:
        # Gamification + automated attendance: a verified checkpoint is both
        # a learning event and the attendance trigger.
        already_awarded = db.execute(
            "SELECT 1 FROM gamification_events WHERE student_id=? AND event_type=? AND description=? LIMIT 1",
            (session["user_id"], "checkpoint", "Completed a video checkpoint successfully.")
        ).fetchone()
        if not already_awarded:
            award_points(session["user_id"], 10, "checkpoint", "Completed a video checkpoint successfully.")
        db.execute("UPDATE daily_learning_goals SET completed_checkpoints=MIN(target_checkpoints,completed_checkpoints+1) WHERE student_id=? AND goal_date=?",
                   (session["user_id"], date.today().isoformat()))
        db.execute("INSERT OR IGNORE INTO attendance(student_id,course_id,attendance_date,status) VALUES(?,?,?,'present')", (session["user_id"], cp["course_id"], date.today().isoformat()))
        update_streak(session["user_id"])
    db.commit()
    completed = db.execute("""SELECT COUNT(*) n FROM checkpoint_attempts ca JOIN checkpoints cp ON cp.id=ca.checkpoint_id
                              WHERE ca.student_id=? AND cp.course_id=? AND ca.correct=1""", (session["user_id"], cp["course_id"])).fetchone()["n"]
    total = db.execute("SELECT COUNT(*) n FROM checkpoints WHERE course_id=?", (cp["course_id"],)).fetchone()["n"]
    return jsonify({"ok": correct, "message": "Correct! You may continue." if correct else "Incorrect answer. Try again.", "attendance_marked": bool(correct), "completed_checkpoints": completed, "total_checkpoints": total})


@app.route("/api/progress/<int:course_id>", methods=["POST"])
@login_required
@role_required("student")
def update_progress(course_id):
    data = request.get_json(silent=True) or {}
    progress = max(0, min(100, float(data.get("progress", 0)))); watched = max(0, float(data.get("watched_seconds", 0)))
    db = get_db(); db.execute("UPDATE enrollments SET progress=?,last_watched=?,completed=? WHERE student_id=? AND course_id=?", (progress, watched, int(progress >= 95), session["user_id"], course_id)); db.commit(); update_streak(session["user_id"])
    return jsonify({"ok": True, "progress": progress})


# ---------------- AI ASSESSMENTS ----------------

@app.route("/api/student/course/<int:course_id>/generate-assessment", methods=["POST"])
@login_required
@role_required("student")
def student_generate_assessment(course_id):
    db = get_db(); student_id = session["user_id"]
    enrolled = db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?", (student_id, course_id)).fetchone()
    if not enrolled:
        return jsonify({"ok": False, "message": "Enroll in this course first."}), 403
    data = request.get_json(silent=True) or {}
    count = max(5, min(30, int(data.get("question_count", 10))))
    difficulty = str(data.get("difficulty", "adaptive"))
    try:
        quiz = generate_ai_quiz(student_id, course_id, count, difficulty)
        assessment_id = save_assessment(course_id, quiz, difficulty)
        return jsonify({"ok": True, "assessment_id": assessment_id, "question_count": len(quiz.questions)})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 500


@app.route("/student/assessments/<int:course_id>")
@login_required
@role_required("student")
def student_assessments(course_id):
    db = get_db(); student_id = session["user_id"]
    enrolled = db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?", (student_id, course_id)).fetchone()
    if not enrolled: flash("Enroll in the course before taking an assessment.", "warning"); return redirect(url_for("course_catalog"))
    course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    assessments = db.execute("SELECT * FROM assessments WHERE course_id=? AND status='published' ORDER BY created_at DESC", (course_id,)).fetchall()
    attempts = db.execute("SELECT * FROM assessment_attempts WHERE student_id=? AND assessment_id IN (SELECT id FROM assessments WHERE course_id=?) ORDER BY completed_at DESC", (student_id, course_id)).fetchall()
    return render_template("student_assessments.html", course=course, assessments=assessments, attempts=attempts, user=current_user())


@app.route("/student/assessment/<int:assessment_id>")
@login_required
@role_required("student")
def take_assessment(assessment_id):
    db = get_db(); student_id = session["user_id"]
    assessment = db.execute("SELECT a.*,c.title course_title,c.id course_id FROM assessments a JOIN courses c ON c.id=a.course_id WHERE a.id=? AND a.status='published'", (assessment_id,)).fetchone()
    if not assessment or not db.execute("SELECT 1 FROM enrollments WHERE student_id=? AND course_id=?", (student_id, assessment["course_id"])).fetchone():
        flash("Assessment unavailable.", "danger"); return redirect(url_for("student_dashboard"))
    questions = db.execute("SELECT id,question,option_a,option_b,option_c,option_d FROM assessment_questions WHERE assessment_id=? ORDER BY id", (assessment_id,)).fetchall()
    return render_template("take_assessment.html", assessment=assessment, questions=questions)


@app.route("/api/assessment/<int:assessment_id>/submit", methods=["POST"])
@login_required
@role_required("student")
def submit_assessment(assessment_id):
    data = request.get_json(silent=True) or {}; answers = data.get("answers", {}); completion_seconds = max(0, float(data.get("completion_seconds", 0)))
    db = get_db(); assessment = db.execute("SELECT * FROM assessments WHERE id=? AND status='published'", (assessment_id,)).fetchone()
    if not assessment: return jsonify({"ok": False, "message": "Assessment not found."}), 404
    questions = db.execute("SELECT * FROM assessment_questions WHERE assessment_id=? ORDER BY id", (assessment_id,)).fetchall()
    if not questions: return jsonify({"ok": False, "message": "This assessment has no questions."}), 400
    correct_count = 0; answer_rows = []
    topic_stats = {}
    for q in questions:
        selected = str(answers.get(str(q["id"]), "")).upper()
        is_correct = selected == q["correct_answer"].upper()
        correct_count += int(is_correct)
        answer_rows.append((q["id"], selected or "-", int(is_correct)))
        topic = q["topic"] or "General"
        topic_stats.setdefault(topic, [0, 0]); topic_stats[topic][0] += 1; topic_stats[topic][1] += int(is_correct)
    score = round(correct_count / len(questions) * 100, 2)
    now = datetime.now().isoformat()
    cur = db.execute("""INSERT INTO assessment_attempts(assessment_id,student_id,score,correct_answers,total_questions,completion_seconds,started_at,completed_at)
                       VALUES(?,?,?,?,?,?,?,?)""", (assessment_id, session["user_id"], score, correct_count, len(questions), completion_seconds, None, now))
    attempt_id = cur.lastrowid
    for qid, selected, ok in answer_rows:
        db.execute("INSERT INTO assessment_answers(attempt_id,question_id,selected_answer,is_correct) VALUES(?,?,?,?)", (attempt_id, qid, selected, ok))
    for topic, (attempts_n, correct_n) in topic_stats.items():
        accuracy = round(correct_n / attempts_n * 100, 2)
        strength = "strong" if accuracy >= 80 else "developing" if accuracy >= 60 else "needs_focus"
        existing = db.execute("SELECT id,attempts,correct_answers FROM learner_topic_performance WHERE student_id=? AND course_id=? AND topic=?", (session["user_id"], assessment["course_id"], topic)).fetchone()
        if existing:
            total_attempts = existing["attempts"] + attempts_n; total_correct = existing["correct_answers"] + correct_n; total_accuracy = round(total_correct / total_attempts * 100, 2)
            db.execute("UPDATE learner_topic_performance SET attempts=?,correct_answers=?,accuracy=?,strength_level=?,last_updated=? WHERE id=?", (total_attempts,total_correct,total_accuracy,"strong" if total_accuracy>=80 else "developing" if total_accuracy>=60 else "needs_focus",now,existing["id"]))
        else:
            db.execute("INSERT INTO learner_topic_performance(student_id,course_id,topic,attempts,correct_answers,accuracy,strength_level,last_updated) VALUES(?,?,?,?,?,?,?,?)", (session["user_id"],assessment["course_id"],topic,attempts_n,correct_n,accuracy,strength,now))
    db.execute("INSERT INTO quiz_results(student_id,course_id,score,completion_seconds,taken_at) VALUES(?,?,?,?,?)", (session["user_id"], assessment["course_id"], score, completion_seconds, now))
    db.execute("UPDATE users SET skill_level=? WHERE id=?", (calculate_level(score), session["user_id"]))
    award_points(session["user_id"], max(5, int(score // 10)), "assessment", f"Completed an AI assessment with a {score:.0f}% score.")
    create_notification(session["user_id"], "Assessment analyzed", f"Your latest score is {score:.0f}%. Your personalized learning path has been refreshed.", "success")
    db.commit(); update_streak(session["user_id"])
    return jsonify({"ok": True, "score": score, "correct": correct_count, "total": len(questions), "skill_level": calculate_level(score), "attempt_id": attempt_id})


@app.route("/student/assessment/result/<int:attempt_id>")
@login_required
@role_required("student")
def assessment_result(attempt_id):
    db = get_db(); attempt = db.execute("""SELECT aa.*,a.title,a.course_id,c.title course_title FROM assessment_attempts aa
        JOIN assessments a ON a.id=aa.assessment_id JOIN courses c ON c.id=a.course_id WHERE aa.id=? AND aa.student_id=?""", (attempt_id,session["user_id"])).fetchone()
    if not attempt: flash("Result not found.", "danger"); return redirect(url_for("student_dashboard"))
    answers = db.execute("""SELECT aq.question,aq.option_a,aq.option_b,aq.option_c,aq.option_d,aq.correct_answer,aq.explanation,aq.topic,aq.learning_objective,asw.selected_answer,asw.is_correct
        FROM assessment_answers asw JOIN assessment_questions aq ON aq.id=asw.question_id WHERE asw.attempt_id=? ORDER BY aq.id""", (attempt_id,)).fetchall()
    topics = db.execute("SELECT topic,accuracy,strength_level FROM learner_topic_performance WHERE student_id=? AND course_id=? ORDER BY accuracy ASC", (session["user_id"],attempt["course_id"])).fetchall()
    return render_template("assessment_result.html", attempt=attempt, answers=answers, topics=topics, user=current_user())


@app.route("/contact-admin", methods=["GET", "POST"])
@login_required
@role_required("student")
def contact_admin():
    db = get_db()
    admin = db.execute("SELECT id, name, email FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
    if not admin:
        flash("No administrator account is available.", "danger")
        return redirect(url_for("student_dashboard"))
    if request.method == "POST":
        subject = request.form.get("subject", "Student Query").strip() or "Student Query"
        message = request.form.get("message", "").strip()
        if not message:
            flash("Please enter your query before sending.", "danger")
            return redirect(url_for("contact_admin"))
        now = datetime.now().isoformat()
        db.execute("INSERT INTO messages(sender_id,recipient_id,subject,message,is_read,created_at) VALUES(?,?,?,?,0,?)",
                   (session["user_id"], admin["id"], subject, message, now))
        db.execute("INSERT INTO notifications(recipient_id,title,message,notification_type,is_read,created_at) VALUES(?,?,?,?,0,?)",
                   (admin["id"], "New student query", f"{current_user()['name']}: {subject}", "info", now))
        db.commit()
        flash("Your query was sent to the administrator.", "success")
        return redirect(url_for("contact_admin"))
    history = db.execute("""SELECT m.*, s.name AS sender_name, r.name AS recipient_name
        FROM messages m JOIN users s ON s.id=m.sender_id JOIN users r ON r.id=m.recipient_id
        WHERE m.sender_id=? OR m.recipient_id=? ORDER BY m.created_at DESC LIMIT 30""",
        (session["user_id"], session["user_id"])).fetchall()
    return render_template("contact_admin.html", admin=admin, history=history)


@app.route("/admin/messages/<int:message_id>/read", methods=["POST"])
@login_required
@role_required("admin")
def admin_message_read(message_id):
    db=get_db()
    db.execute("UPDATE messages SET is_read=1 WHERE id=? AND recipient_id=?", (message_id, session["user_id"]))
    db.commit()
    return redirect(url_for("admin_dashboard") + "#student-messages")


@app.route("/admin/messages/<int:message_id>/reply", methods=["POST"])
@login_required
@role_required("admin")
def admin_message_reply(message_id):
    db=get_db()
    original=db.execute("SELECT * FROM messages WHERE id=? AND recipient_id=?", (message_id, session["user_id"])).fetchone()
    if not original:
        flash("Message not found.", "danger")
        return redirect(url_for("admin_dashboard"))
    reply=request.form.get("message", "").strip()
    if not reply:
        flash("Reply cannot be empty.", "danger")
        return redirect(url_for("admin_dashboard") + "#student-messages")
    now=datetime.now().isoformat()
    subject="Re: " + (original["subject"] or "Student Query")
    # The SQL statements below hard-code is_read=0, so only five values
    # must be supplied for each INSERT.
    db.execute("INSERT INTO messages(sender_id,recipient_id,subject,message,is_read,created_at) VALUES(?,?,?,?,0,?)",
               (session["user_id"], original["sender_id"], subject, reply, now))
    db.execute("INSERT INTO notifications(recipient_id,title,message,notification_type,is_read,created_at) VALUES(?,?,?,?,0,?)",
               (original["sender_id"], "Administrator replied", reply[:180], "success", now))
    db.execute("UPDATE messages SET is_read=1 WHERE id=?", (message_id,))
    db.commit()
    flash("Reply sent to the student.", "success")
    return redirect(url_for("admin_dashboard") + "#student-messages")


# ---------------- ADMIN ----------------

@app.route("/admin")
@login_required
@role_required("admin")
def admin_dashboard():
    db = get_db()
    stats = db.execute("""SELECT
        (SELECT COUNT(*) FROM users WHERE role='student') students,
        (SELECT COUNT(*) FROM courses) courses,
        (SELECT COUNT(*) FROM courses WHERE published=1) published,
        (SELECT COUNT(*) FROM enrollments) enrollments,
        (SELECT COUNT(*) FROM assessment_attempts) attempts,
        (SELECT COALESCE(AVG(score),0) FROM assessment_attempts) avg_score""").fetchone()
    courses = db.execute("SELECT c.*, (SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id) learners, (SELECT COUNT(*) FROM assessments a WHERE a.course_id=c.id) assessments FROM courses c ORDER BY c.id DESC").fetchall()
    messages = db.execute("""SELECT m.*, u.name AS sender_name, u.email AS sender_email
        FROM messages m JOIN users u ON u.id=m.sender_id
        WHERE m.recipient_id=? ORDER BY m.is_read ASC, m.created_at DESC LIMIT 20""", (session["user_id"],)).fetchall()
    unread_messages = db.execute("SELECT COUNT(*) AS n FROM messages WHERE recipient_id=? AND is_read=0", (session["user_id"],)).fetchone()["n"]
    return render_template("admin_dashboard.html", stats=stats, courses=courses, messages=messages, unread_messages=unread_messages)


@app.route("/admin/course/new", methods=["GET","POST"])
@login_required
@role_required("admin")
def admin_course_new():
    if request.method == "POST":
        db = get_db(); cur = db.execute("""INSERT INTO courses(title,description,category,level,career_target,video_url,published,created_at)
          VALUES(?,?,?,?,?,?,?,?)""", (request.form["title"].strip(),request.form["description"].strip(),request.form.get("category","General").strip(),request.form["level"],request.form.get("career_target","").strip(),request.form.get("video_url","").strip(),int(request.form.get("published")=="1"),datetime.now().isoformat())); db.commit(); flash("Course created.","success"); return redirect(url_for("admin_course_edit",course_id=cur.lastrowid))
    return render_template("course_form.html", course=None)


@app.route("/admin/course/<int:course_id>/edit", methods=["GET","POST"])
@login_required
@role_required("admin")
def admin_course_edit(course_id):
    db=get_db(); course=db.execute("SELECT * FROM courses WHERE id=?",(course_id,)).fetchone()
    if not course: flash("Course not found.","danger"); return redirect(url_for("admin_dashboard"))
    if request.method=="POST":
        db.execute("UPDATE courses SET title=?,description=?,category=?,level=?,career_target=?,video_url=?,published=? WHERE id=?",(request.form["title"].strip(),request.form["description"].strip(),request.form.get("category","General").strip(),request.form["level"],request.form.get("career_target","").strip(),request.form.get("video_url","").strip(),int(request.form.get("published")=="1"),course_id)); db.commit(); flash("Course updated.","success"); return redirect(url_for("admin_course_edit",course_id=course_id))
    checkpoints=db.execute("SELECT * FROM checkpoints WHERE course_id=? ORDER BY timestamp_seconds",(course_id,)).fetchall(); assessments=db.execute("SELECT * FROM assessments WHERE course_id=? ORDER BY created_at DESC",(course_id,)).fetchall()
    return render_template("course_form.html",course=course,checkpoints=checkpoints,assessments=assessments)


@app.route("/admin/course/<int:course_id>/delete",methods=["POST"])
@login_required
@role_required("admin")
def admin_course_delete(course_id):
    db=get_db(); db.execute("DELETE FROM courses WHERE id=?",(course_id,)); db.commit(); flash("Course deleted.","success"); return redirect(url_for("admin_dashboard"))


@app.route("/admin/course/<int:course_id>/checkpoint/add",methods=["POST"])
@login_required
@role_required("admin")
def admin_checkpoint_add(course_id):
    db=get_db(); db.execute("INSERT INTO checkpoints(course_id,timestamp_seconds,question,option_a,option_b,option_c,option_d,correct_option) VALUES(?,?,?,?,?,?,?,?)",(course_id,float(request.form["timestamp_seconds"]),request.form["question"].strip(),request.form["option_a"].strip(),request.form["option_b"].strip(),request.form["option_c"].strip(),request.form["option_d"].strip(),request.form["correct_option"].upper())); db.commit(); flash("Checkpoint added.","success"); return redirect(url_for("admin_course_edit",course_id=course_id))


@app.route("/admin/checkpoint/<int:checkpoint_id>/delete",methods=["POST"])
@login_required
@role_required("admin")
def admin_checkpoint_delete(checkpoint_id):
    db=get_db(); cp=db.execute("SELECT course_id FROM checkpoints WHERE id=?",(checkpoint_id,)).fetchone()
    if cp: db.execute("DELETE FROM checkpoints WHERE id=?",(checkpoint_id,)); db.commit(); return redirect(url_for("admin_course_edit",course_id=cp["course_id"]))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/course/<int:course_id>/ai-generate",methods=["POST"])
@login_required
@role_required("admin")
def admin_ai_generate(course_id):
    count=max(5,min(30,int(request.form.get("question_count",10)))); difficulty=request.form.get("difficulty","adaptive")
    # Use an admin's context while generating a course-level assessment. The generator uses a real learner profile only if available.
    learner=request.form.get("student_id")
    student_id=int(learner) if learner else None
    # Course-level generation intentionally works without an enrolled learner.
    try:
        quiz=generate_ai_quiz(student_id,course_id,count,difficulty,admin_id=session["user_id"]); aid=save_assessment(course_id,quiz,difficulty); flash(f"AI assessment generated with {len(quiz.questions)} questions.","success")
    except Exception as exc:
        flash(str(exc),"danger")
    return redirect(url_for("admin_course_edit",course_id=course_id))


def db_student_id_for_course(course_id):
    row=get_db().execute("SELECT u.id FROM users u JOIN enrollments e ON e.student_id=u.id WHERE e.course_id=? AND u.role='student' ORDER BY u.id LIMIT 1",(course_id,)).fetchone()
    return row["id"] if row else None


@app.route("/admin/assessment/<int:assessment_id>/delete",methods=["POST"])
@login_required
@role_required("admin")
def admin_assessment_delete(assessment_id):
    db=get_db(); row=db.execute("SELECT course_id FROM assessments WHERE id=?",(assessment_id,)).fetchone()
    if row: db.execute("DELETE FROM assessments WHERE id=?",(assessment_id,)); db.commit(); flash("Assessment deleted.","success"); return redirect(url_for("admin_course_edit",course_id=row["course_id"]))
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/students")
@login_required
@role_required("admin")
def admin_students():
    students=get_db().execute("""SELECT u.*,(SELECT COUNT(*) FROM enrollments e WHERE e.student_id=u.id) enrolled_count,
      (SELECT COALESCE(AVG(score),0) FROM assessment_attempts q WHERE q.student_id=u.id) avg_score,
      (SELECT COUNT(*) FROM assessment_attempts q WHERE q.student_id=u.id) attempts FROM users u WHERE role='student' ORDER BY u.id DESC""").fetchall()
    return render_template("admin_students.html",students=students)


@app.route("/admin/student/<int:student_id>")
@login_required
@role_required("admin")
def admin_student_detail(student_id):
    db=get_db(); student=db.execute("SELECT * FROM users WHERE id=? AND role='student'",(student_id,)).fetchone()
    if not student: flash("Student not found.","danger"); return redirect(url_for("admin_students"))
    courses=db.execute("SELECT c.title,e.progress,e.completed,e.enrolled_at FROM enrollments e JOIN courses c ON c.id=e.course_id WHERE e.student_id=?",(student_id,)).fetchall()
    quizzes=db.execute("SELECT c.title,q.score,q.completion_seconds,q.taken_at FROM quiz_results q JOIN courses c ON c.id=q.course_id WHERE q.student_id=? ORDER BY q.taken_at DESC",(student_id,)).fetchall()
    topics=db.execute("SELECT c.title,t.topic,t.accuracy,t.strength_level FROM learner_topic_performance t JOIN courses c ON c.id=t.course_id WHERE t.student_id=? ORDER BY t.accuracy",(student_id,)).fetchall()
    return render_template("admin_student_detail.html",student=student,courses=courses,quizzes=quizzes,topics=topics)


@app.cli.command("init-db")
def init_db_command():
    init_db(); print(f"Database initialized at {DB_PATH}")



@app.route("/admin/ai-assessment", methods=["GET", "POST"], endpoint="admin_ai_assessment")
@login_required
@role_required("admin")
def admin_ai_assessment():
    """Generate and persist course-specific MCQ assessments with Gemini."""
    db = get_db()
    courses = db.execute("SELECT * FROM courses ORDER BY title COLLATE NOCASE").fetchall()
    questions = []
    selected_course = None
    selected_topic = ""
    difficulty = "adaptive"

    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        selected_topic = request.form.get("topic", "").strip()
        difficulty = request.form.get("difficulty", "adaptive").strip().lower()
        count = max(5, min(request.form.get("question_count", type=int) or 10, 30))

        selected_course = db.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
        if not selected_course:
            flash("Please select a valid course.", "danger")
            return render_template("admin_ai_assessment.html", courses=courses, questions=[],
                                   selected_course=None, selected_topic=selected_topic,
                                   difficulty=difficulty)

        try:
            # Use the same validated generator as the rest of the platform so
            # AI assessments have one consistent database schema and workflow.
            quiz = generate_ai_quiz(None, course_id, count, difficulty, admin_id=session["user_id"])
            assessment_id = save_assessment(course_id, quiz, difficulty)
            questions = [
                {
                    "question": q.question,
                    "options": [q.option_a, q.option_b, q.option_c, q.option_d],
                    "answer": q.correct_answer,
                    "explanation": q.explanation,
                    "topic": q.topic,
                    "difficulty": q.difficulty,
                }
                for q in quiz.questions
            ]
            flash(f"AI assessment created successfully with {len(questions)} questions (Assessment #{assessment_id}).", "success")
        except Exception as exc:
            flash(f"AI assessment generation failed: {exc}", "danger")

    return render_template("admin_ai_assessment.html", courses=courses,
                           questions=questions, selected_course=selected_course,
                           selected_topic=selected_topic, difficulty=difficulty)


if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True, host="127.0.0.1", port=5000)

