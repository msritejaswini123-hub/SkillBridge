"""
app.py
======
SkillBridge - Academia-Industry Collaboration Portal.

Run it with:      python app.py
Different port:   python app.py --port 5001

Everything is wired end to end:
    browser form -> Flask route -> parameterised SQL -> recommendation engine
                 -> Jinja template -> browser

SECURITY NOTES
  * passwords are hashed with werkzeug (never stored in plain text)
  * login state lives in a signed Flask session cookie
  * @role_required blocks a student from opening a company page and vice versa
  * every SQL statement uses ? placeholders
  * uploads must be .pdf, must really start with %PDF, and are capped at 5 MB
"""

import os
import sys
import time
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import analytics
import database as db
import resume_parser as rp
from recommendation import (SORT_OPTIONS, WEIGHTS, load_internships,
                            rank_candidates, recommend_for_student,
                            refresh_skill_gaps, save_application, score_match,
                            skill_gap_report, sort_results)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
MAX_UPLOAD_BYTES = 5 * 1024 * 1024          # 5 MB
ALLOWED_EXTENSIONS = {".pdf"}

APPLICATION_STATUSES = ["Applied", "Under Review", "Shortlisted", "Selected", "Rejected"]

app = Flask(__name__)
# In a real deployment this comes from an environment variable.
app.config["SECRET_KEY"] = os.environ.get("SKILLBRIDGE_SECRET", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ===========================================================================
# DATABASE PER REQUEST
# ===========================================================================

def get_db():
    """One connection per request, closed automatically afterwards."""
    if "db" not in g:
        g.db = db.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exception):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# Guard so the check below runs once per process, not on every request.
_DB_READY = {"done": False}


@app.before_request
def ensure_database_ready():
    """
    Create the tables and demo data on the first request if they are missing.

    Running locally you use `python init_db.py`, so this does nothing. It exists
    for hosted/ephemeral filesystems (Render, Railway, Docker) where the SQLite
    file does not survive a restart - without it the site would serve
    "no such table: users" after every redeploy.

    Both steps are idempotent: CREATE TABLE IF NOT EXISTS, and the seed is
    skipped when any user already exists.
    """
    if _DB_READY["done"]:
        return
    _DB_READY["done"] = True
    try:
        import seed_data
        db.init_db()
        conn = get_db()
        if not seed_data.is_seeded(conn):
            app.logger.info("Empty database detected - inserting demo data.")
            seed_data.seed(conn, verbose=False)
    except Exception:
        # Log it for the host's console; the error pages handle the user side.
        app.logger.exception("Could not prepare the database")


# ===========================================================================
# AUTH HELPERS
# ===========================================================================

def current_user():
    """The logged-in users row, or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    if "user" not in g:
        g.user = db.query_one(get_db(), "SELECT * FROM users WHERE id = ?", (user_id,))
        if g.user is None:
            session.clear()          # the account was deleted underneath us
    return g.user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Role based authorisation - a student cannot open company pages."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login", next=request.path))
            if user["role"] not in roles:
                flash("That page is not available for your account type.", "danger")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def student_profile_or_404():
    """The logged-in student's profile row."""
    profile = db.query_one(
        get_db(), "SELECT * FROM student_profiles WHERE user_id = ?", (session["user_id"],))
    if not profile:
        abort(404, "Student profile not found.")
    return profile


def company_or_404():
    company = db.query_one(
        get_db(), "SELECT * FROM companies WHERE user_id = ?", (session["user_id"],))
    if not company:
        abort(404, "Company profile not found.")
    return company


# ===========================================================================
# SMALL INPUT VALIDATION HELPERS
# ===========================================================================

def clean_text(value, max_length=300):
    """Trim, collapse newlines-only input, and cap the length."""
    if value is None:
        return ""
    return " ".join(str(value).split())[:max_length]


def clean_block(value, max_length=4000):
    """Same, but keeps line breaks (for descriptions)."""
    if value is None:
        return ""
    lines = [" ".join(line.split()) for line in str(value).splitlines()]
    return "\n".join(lines).strip()[:max_length]


def to_int(value, default=0, minimum=0, maximum=10_000_000):
    try:
        number = int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(number, maximum))


def split_skills(raw):
    """'Python, SQL; Flask' -> ['Python', 'SQL', 'Flask'] (normalised, de-duplicated)."""
    if not raw:
        return []
    parts = str(raw).replace(";", ",").replace("\n", ",").split(",")
    out = []
    for part in parts:
        name = rp.normalize_skill(part)
        if name and name not in out:
            out.append(name)
    return out[:40]


def profile_completion(profile, skill_count):
    """A simple 0-100% score so the dashboard can nudge the student."""
    if not profile:
        return 0
    checks = [
        bool(profile["qualification"]),
        bool(profile["branch"]),
        bool(profile["graduation_year"]),
        bool(profile["preferred_location"]),
        bool(profile["min_stipend"] or profile["max_stipend"]),
        bool(profile["college"]),
        bool(profile["phone"]),
        bool(profile["resume_text"]),
        bool(profile["projects_text"]),
        skill_count > 0,
    ]
    return int(round(100 * sum(checks) / len(checks)))


# ===========================================================================
# TEMPLATE GLOBALS
# ===========================================================================

@app.context_processor
def inject_globals():
    user = current_user()
    return {
        "current_user": user,
        "user_role": user["role"] if user else None,
        "weights": WEIGHTS,
        "app_name": "SkillBridge",
        "statuses": APPLICATION_STATUSES,
    }


@app.template_filter("rupees")
def rupees(value):
    """15000 -> '15,000'"""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


@app.template_filter("stipend_range")
def stipend_range(internship):
    """Human stipend text for a card."""
    low = internship["stipend_min"] or 0
    high = internship["stipend_max"] or 0
    if not low and not high:
        return "Not disclosed"
    if not low or low == high:
        return f"Rs {max(low, high):,}/month"
    return f"Rs {low:,} - {high:,}/month"


@app.template_filter("score_class")
def score_class(score):
    """Bucket a match % so the UI can label it (never colour alone)."""
    score = score or 0
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "strong"
    if score >= 50:
        return "moderate"
    return "low"


def filter_options():
    """Distinct locations/domains/skills for the filter dropdowns."""
    conn = get_db()
    return {
        "locations": [r["location"] for r in db.query_all(
            conn, "SELECT DISTINCT location FROM internships WHERE is_active = 1 "
                  "AND location != '' ORDER BY location")],
        "domains": [r["domain"] for r in db.query_all(
            conn, "SELECT DISTINCT domain FROM internships WHERE is_active = 1 "
                  "AND domain != '' ORDER BY domain")],
        "skills": [r["name"] for r in db.query_all(
            conn, """SELECT DISTINCT s.name FROM skills s
                     JOIN internship_skills i ON i.skill_id = s.id ORDER BY s.name""")],
    }


def read_sort():
    """Which ordering the user asked for ('match' by default, 'ml' to re-rank)."""
    value = request.args.get("sort", "match")
    return value if value in SORT_OPTIONS else "match"


def read_filters():
    """Pull the filter values out of the query string."""
    return {
        "q": clean_text(request.args.get("q"), 80),
        "location": clean_text(request.args.get("location"), 60),
        "domain": clean_text(request.args.get("domain"), 60),
        "skill": clean_text(request.args.get("skill"), 60),
        "min_stipend": to_int(request.args.get("min_stipend"), 0, 0, 500000),
        "duration": to_int(request.args.get("duration"), 0, 0, 24),
    }


# ===========================================================================
# PUBLIC PAGES
# ===========================================================================

@app.route("/")
def index():
    conn = get_db()
    stats = analytics.counts(conn)
    featured = load_internships(conn)[:6]
    skills_map = db.all_internship_skills(conn)
    cards = [{"internship": row, "skills": skills_map.get(row["id"], {}), "match": None}
             for row in featured]
    return render_template(
        "index.html", stats=stats, cards=cards,
        demand=analytics.industry_skill_demand(conn, 8),
        domains=analytics.popular_domains(conn)[:6],
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        role = request.form.get("role", "student")
        name = clean_text(request.form.get("name"), 100)
        email = clean_text(request.form.get("email"), 120).lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""

        errors = []
        if role not in ("student", "company", "academia"):
            errors.append("Please choose a valid account type.")
        if len(name) < 2:
            errors.append("Please enter your full name.")
        if "@" not in email or "." not in email.split("@")[-1]:
            errors.append("Please enter a valid email address.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm:
            errors.append("The two passwords do not match.")

        conn = get_db()
        if not errors and db.query_one(conn, "SELECT id FROM users WHERE email = ?", (email,)):
            errors.append("An account with that email already exists. Try logging in.")

        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("register.html", form=request.form), 400

        cursor = db.execute(
            conn,
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role),
        )
        user_id = cursor.lastrowid

        # Create the matching role table row so later pages always find one.
        if role == "student":
            db.execute(conn, "INSERT INTO student_profiles (user_id) VALUES (?)", (user_id,))
        elif role == "company":
            company_name = clean_text(request.form.get("company_name"), 120) or name
            db.execute(
                conn,
                "INSERT INTO companies (user_id, company_name, location) VALUES (?, ?, ?)",
                (user_id, company_name, clean_text(request.form.get("location"), 60)),
            )
        else:
            college = clean_text(request.form.get("college_name"), 150) or name
            db.execute(
                conn, "INSERT INTO academia (user_id, college_name) VALUES (?, ?)",
                (user_id, college),
            )

        session.clear()
        session["user_id"] = user_id
        flash(f"Welcome to SkillBridge, {name}! Your account is ready.", "success")
        if role == "student":
            flash("Next step: upload your resume so we can build your skill profile.", "info")
        return redirect(url_for("dashboard"))

    return render_template("register.html", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = clean_text(request.form.get("email"), 120).lower()
        password = request.form.get("password") or ""
        user = db.query_one(get_db(), "SELECT * FROM users WHERE email = ?", (email,))

        # One generic message for both cases - never reveal whether the email exists.
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "danger")
            return render_template("login.html", email=email), 401

        session.clear()
        session["user_id"] = user["id"]
        flash(f"Logged in as {user['name']}.", "success")
        destination = request.args.get("next") or request.form.get("next")
        if destination and destination.startswith("/"):    # never redirect off-site
            return redirect(destination)
        return redirect(url_for("dashboard"))

    return render_template("login.html", email="")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Send each role to its own dashboard."""
    role = current_user()["role"]
    return redirect(url_for({
        "student": "student_dashboard",
        "company": "company_dashboard",
        "academia": "academia_dashboard",
    }[role]))


@app.route("/ml-info")
def ml_info():
    """Transparency page: exactly what the ML layer is and what it trained on."""
    from ml.model import model_info
    return render_template("ml_info.html", info=model_info(), weights=WEIGHTS)


# ===========================================================================
# STUDENT
# ===========================================================================

@app.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    conn = get_db()
    profile = student_profile_or_404()
    skills = db.student_skill_names(conn, profile["id"])

    # 3, not 4: the card grid is 3 columns at desktop width, so 4 leaves an orphan.
    recommendations = recommend_for_student(conn, profile, limit=3) if skills else []
    if skills:
        # Recompute the cached gaps from the full ranked list.
        refresh_skill_gaps(conn, profile["id"], recommend_for_student(conn, profile))

    applications = db.query_all(
        conn,
        """SELECT a.*, i.title, i.location, c.company_name
           FROM applications a
           JOIN internships i ON i.id = a.internship_id
           JOIN companies c   ON c.id = i.company_id
           WHERE a.student_id = ? ORDER BY a.applied_at DESC, a.id DESC LIMIT 5""",
        (profile["id"],),
    )
    saved_count = db.query_one(
        conn, "SELECT COUNT(*) AS n FROM saved_internships WHERE student_id = ?",
        (profile["id"],))["n"]

    return render_template(
        "student_dashboard.html",
        profile=profile, skills=skills,
        completion=profile_completion(profile, len(skills)),
        recommendations=recommendations,
        gaps=skill_gap_report(conn, profile["id"])[:5],
        applications=applications,
        saved_count=saved_count,
        total_internships=analytics.counts(conn)["internships"],
    )


@app.route("/student/profile", methods=["GET", "POST"])
@role_required("student")
def student_profile():
    conn = get_db()
    profile = student_profile_or_404()

    if request.method == "POST":
        qualification = clean_text(request.form.get("qualification"), 40)
        branch = clean_text(request.form.get("branch"), 60)
        graduation_year = to_int(request.form.get("graduation_year"), 0, 1990, 2040)
        min_stipend = to_int(request.form.get("min_stipend"), 0, 0, 500000)
        max_stipend = to_int(request.form.get("max_stipend"), 0, 0, 500000)

        if max_stipend and min_stipend > max_stipend:
            min_stipend, max_stipend = max_stipend, min_stipend
            flash("Your stipend range was the wrong way round, so we swapped it.", "info")

        db.execute(
            conn,
            """UPDATE student_profiles SET
                 college = ?, qualification = ?, branch = ?, graduation_year = ?,
                 preferred_location = ?, min_stipend = ?, max_stipend = ?, phone = ?,
                 experience_months = ?, projects_text = ?, updated_at = datetime('now')
               WHERE id = ?""",
            (clean_text(request.form.get("college"), 150), qualification, branch,
             graduation_year or None,
             clean_text(request.form.get("preferred_location"), 60),
             min_stipend, max_stipend,
             clean_text(request.form.get("phone"), 20),
             to_int(request.form.get("experience_months"), 0, 0, 120),
             clean_block(request.form.get("projects_text"), 2000),
             profile["id"]),
        )
        flash("Profile saved. Your recommendations have been updated.", "success")
        return redirect(url_for("student_profile"))

    skills = db.student_skill_names(conn, profile["id"])
    return render_template(
        "profile.html", profile=profile, skills=skills,
        completion=profile_completion(profile, len(skills)),
        locations=filter_options()["locations"],
        degrees=sorted(set(rp.DEGREE_ALIASES.values())),
        branches=sorted(set(rp.BRANCH_ALIASES.values())),
    )


@app.route("/student/resume", methods=["GET", "POST"])
@role_required("student")
def student_resume():
    conn = get_db()
    profile = student_profile_or_404()

    if request.method == "POST":
        upload = request.files.get("resume")

        # ---- validate the upload ----
        if not upload or not upload.filename:
            flash("Please choose a PDF file first.", "danger")
            return redirect(url_for("student_resume"))

        extension = os.path.splitext(upload.filename)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            flash("Only PDF resumes are accepted (.pdf).", "danger")
            return redirect(url_for("student_resume"))

        header = upload.stream.read(5)
        upload.stream.seek(0)
        if header != b"%PDF-":
            flash("That file is not a real PDF, even though it is named .pdf.", "danger")
            return redirect(url_for("student_resume"))

        safe_name = secure_filename(upload.filename) or "resume.pdf"
        stored_name = f"student{profile['id']}_{int(time.time())}_{safe_name}"
        destination = os.path.join(app.config["UPLOAD_FOLDER"], stored_name)

        try:
            upload.save(destination)
        except OSError:
            flash("The file could not be saved. Please try again.", "danger")
            return redirect(url_for("student_resume"))

        # ---- parse it ----
        try:
            parsed = rp.parse_resume(destination)
        except rp.ResumeError as error:
            os.remove(destination) if os.path.exists(destination) else None
            flash(str(error), "danger")
            return redirect(url_for("student_resume"))
        except Exception:
            os.remove(destination) if os.path.exists(destination) else None
            flash("Something went wrong while reading that PDF. Please try another file.",
                  "danger")
            return redirect(url_for("student_resume"))

        # Remove the previous file so uploads/ does not fill up.
        if profile["resume_filename"]:
            old = os.path.join(app.config["UPLOAD_FOLDER"], profile["resume_filename"])
            if os.path.exists(old) and profile["resume_filename"] != stored_name:
                try:
                    os.remove(old)
                except OSError:
                    pass

        db.execute(
            conn,
            """UPDATE student_profiles SET resume_filename = ?, resume_text = ?,
                 projects_text = CASE WHEN ? != '' THEN ? ELSE projects_text END,
                 experience_months = CASE WHEN ? > 0 THEN ? ELSE experience_months END,
                 updated_at = datetime('now')
               WHERE id = ?""",
            (stored_name, parsed["text"], parsed["projects"], parsed["projects"],
             parsed["experience_months"], parsed["experience_months"], profile["id"]),
        )

        # Hand the extracted values to the review screen.
        session["extracted"] = {
            "skills": parsed["skills"],
            "degree": parsed["degree"] or "",
            "branch": parsed["branch"] or "",
            "experience_months": parsed["experience_months"],
        }
        if not parsed["skills"]:
            flash("We read the PDF but did not recognise any skills from our dictionary. "
                  "You can add them manually below.", "warning")
        else:
            flash(f"Resume read successfully - {len(parsed['skills'])} skills found. "
                  "Please review them before saving.", "success")
        return redirect(url_for("student_skills"))

    return render_template(
        "resume.html", profile=profile,
        skills=db.student_skill_names(conn, profile["id"]),
        max_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
        library_size=len(rp.all_skill_names()),
        sample_exists=os.path.exists(os.path.join(BASE_DIR, "sample_data", "sample_resume.pdf")),
    )


@app.route("/student/resume/file")
@role_required("student")
def student_resume_file():
    """Let a student download their OWN resume back (never anyone else's)."""
    profile = student_profile_or_404()
    if not profile["resume_filename"]:
        abort(404, "No resume uploaded yet.")
    return send_from_directory(app.config["UPLOAD_FOLDER"], profile["resume_filename"],
                              as_attachment=False)


@app.route("/student/skills", methods=["GET", "POST"])
@role_required("student")
def student_skills():
    conn = get_db()
    profile = student_profile_or_404()

    if request.method == "POST":
        # Checkboxes that survived the review + anything typed in the free text box.
        kept = request.form.getlist("skill")
        typed = split_skills(request.form.get("extra_skills"))
        final = []
        for name in [rp.normalize_skill(s) for s in kept] + typed:
            if name and name not in final:
                final.append(name)

        if not final:
            flash("Please keep at least one skill so we can recommend internships.",
                  "warning")
            return redirect(url_for("student_skills"))

        # Replace the student's skill set with the reviewed list.
        db.execute(conn, "DELETE FROM student_skills WHERE student_id = ?", (profile["id"],))
        source_map = {s.lower(): "resume" for s in session.get("extracted", {}).get("skills", [])}
        for name in final:
            skill_id = db.get_or_create_skill(conn, name, rp.skill_category(name))
            db.execute(
                conn,
                """INSERT OR IGNORE INTO student_skills (student_id, skill_id, source)
                   VALUES (?, ?, ?)""",
                (profile["id"], skill_id, source_map.get(name.lower(), "manual")),
            )

        # Optionally accept the qualification the parser suggested.
        if request.form.get("apply_qualification"):
            extracted = session.get("extracted", {})
            db.execute(
                conn,
                """UPDATE student_profiles SET qualification = ?, branch = ?
                   WHERE id = ?""",
                (clean_text(request.form.get("degree") or extracted.get("degree"), 40),
                 clean_text(request.form.get("branch") or extracted.get("branch"), 60),
                 profile["id"]),
            )

        session.pop("extracted", None)
        refresh_skill_gaps(conn, profile["id"], recommend_for_student(conn, profile))
        flash(f"Saved {len(final)} skills to your profile.", "success")
        return redirect(url_for("student_recommendations"))

    saved = db.query_all(
        conn,
        """SELECT s.name, s.category, ss.source FROM student_skills ss
           JOIN skills s ON s.id = ss.skill_id
           WHERE ss.student_id = ? ORDER BY s.category, s.name""",
        (profile["id"],),
    )
    extracted = session.get("extracted")
    return render_template(
        "skills.html", profile=profile, saved=saved, extracted=extracted,
        all_skills=rp.all_skill_names(),
        library_size=len(rp.all_skill_names()),
    )


@app.route("/student/recommendations")
@role_required("student")
def student_recommendations():
    conn = get_db()
    profile = student_profile_or_404()
    skills = db.student_skill_names(conn, profile["id"])
    filters = read_filters()
    sort_by = read_sort()

    results = recommend_for_student(conn, profile, filters=filters,
                                   sort_by=sort_by) if skills else []
    if skills and not any(filters.values()):
        refresh_skill_gaps(conn, profile["id"], results)

    skills_map = db.all_internship_skills(conn)
    saved_ids = {r["internship_id"] for r in db.query_all(
        conn, "SELECT internship_id FROM saved_internships WHERE student_id = ?",
        (profile["id"],))}
    applied_ids = {r["internship_id"] for r in db.query_all(
        conn, "SELECT internship_id FROM applications WHERE student_id = ?",
        (profile["id"],))}

    cards = [{
        "internship": entry["internship"],
        "match": entry["match"],
        "skills": skills_map.get(entry["internship"]["id"], {}),
        "saved": entry["internship"]["id"] in saved_ids,
        "applied": entry["internship"]["id"] in applied_ids,
    } for entry in results]

    return render_template(
        "recommendations.html", profile=profile, skills=skills, cards=cards,
        filters=filters, options=filter_options(),
        sort_by=sort_by, sort_options=SORT_OPTIONS,
    )


@app.route("/student/skill-gap")
@role_required("student")
def student_skill_gap():
    conn = get_db()
    profile = student_profile_or_404()
    skills = db.student_skill_names(conn, profile["id"])
    if skills:
        refresh_skill_gaps(conn, profile["id"], recommend_for_student(conn, profile))
    return render_template(
        "skill_gap.html", profile=profile, skills=skills,
        report=skill_gap_report(conn, profile["id"]),
        demand=analytics.industry_skill_demand(conn, 10),
    )


@app.route("/student/applications")
@role_required("student")
def student_applications():
    conn = get_db()
    profile = student_profile_or_404()
    rows = db.query_all(
        conn,
        """SELECT a.*, i.title, i.location, i.domain, i.duration_months,
                  i.stipend_min, i.stipend_max, c.company_name
           FROM applications a
           JOIN internships i ON i.id = a.internship_id
           JOIN companies c   ON c.id = i.company_id
           WHERE a.student_id = ?
           ORDER BY a.applied_at DESC, a.id DESC""",
        (profile["id"],),
    )
    return render_template("applications.html", profile=profile, applications=rows)


@app.route("/student/saved")
@role_required("student")
def student_saved():
    conn = get_db()
    profile = student_profile_or_404()
    rows = db.query_all(
        conn,
        """SELECT i.*, c.company_name, s.saved_at
           FROM saved_internships s
           JOIN internships i ON i.id = s.internship_id
           JOIN companies c   ON c.id = i.company_id
           WHERE s.student_id = ? ORDER BY s.saved_at DESC""",
        (profile["id"],),
    )
    student_skills = db.student_skill_names(conn, profile["id"])
    skills_map = db.all_internship_skills(conn)
    applied_ids = {r["internship_id"] for r in db.query_all(
        conn, "SELECT internship_id FROM applications WHERE student_id = ?",
        (profile["id"],))}
    cards = [{
        "internship": row,
        "skills": skills_map.get(row["id"], {}),
        "match": score_match(profile, row, student_skills, skills_map.get(row["id"], {}))
                 if student_skills else None,
        "saved": True,
        "applied": row["id"] in applied_ids,
    } for row in rows]
    return render_template("saved.html", profile=profile, cards=cards)


# ===========================================================================
# INTERNSHIP LISTING & DETAIL  (public, richer when a student is logged in)
# ===========================================================================

@app.route("/internships")
def internships():
    conn = get_db()
    filters = read_filters()
    rows = load_internships(conn, filters)
    skills_map = db.all_internship_skills(conn)

    user = current_user()
    profile, student_skills, saved_ids, applied_ids = None, [], set(), set()
    if user and user["role"] == "student":
        profile = db.query_one(
            conn, "SELECT * FROM student_profiles WHERE user_id = ?", (user["id"],))
        if profile:
            student_skills = db.student_skill_names(conn, profile["id"])
            saved_ids = {r["internship_id"] for r in db.query_all(
                conn, "SELECT internship_id FROM saved_internships WHERE student_id = ?",
                (profile["id"],))}
            applied_ids = {r["internship_id"] for r in db.query_all(
                conn, "SELECT internship_id FROM applications WHERE student_id = ?",
                (profile["id"],))}

    cards = []
    for row in rows:
        skills = skills_map.get(row["id"], {})
        match = None
        if profile and student_skills:
            match = score_match(profile, row, student_skills, skills)
        cards.append({
            "internship": row, "skills": skills, "match": match,
            "saved": row["id"] in saved_ids, "applied": row["id"] in applied_ids,
        })

    if profile and student_skills:
        sort_results(cards, read_sort())

    return render_template("internships.html", cards=cards, filters=filters,
                           options=filter_options(), profile=profile)


@app.route("/internship/<int:internship_id>")
def internship_detail(internship_id):
    conn = get_db()
    internship = db.query_one(
        conn,
        """SELECT i.*, c.company_name, c.industry, c.website, c.about, c.location AS hq
           FROM internships i JOIN companies c ON c.id = i.company_id
           WHERE i.id = ?""",
        (internship_id,),
    )
    if not internship:
        abort(404, "That internship does not exist or has been removed.")

    skills = db.internship_skill_map(conn, internship_id)
    user = current_user()
    match, profile, already_applied, is_saved, courses = None, None, False, False, []

    if user and user["role"] == "student":
        profile = db.query_one(
            conn, "SELECT * FROM student_profiles WHERE user_id = ?", (user["id"],))
        if profile:
            student_skills = db.student_skill_names(conn, profile["id"])
            if student_skills:
                match = score_match(profile, internship, student_skills, skills)
                # Courses for the skills this student is missing.
                for name in match["missing_skills"]:
                    rows = db.query_all(
                        conn,
                        """SELECT c.*, s.name AS skill FROM courses c
                           JOIN skills s ON s.id = c.skill_id
                           WHERE s.name = ? COLLATE NOCASE LIMIT 2""",
                        (name,),
                    )
                    courses.extend(rows)
            already_applied = bool(db.query_one(
                conn, "SELECT id FROM applications WHERE student_id = ? AND internship_id = ?",
                (profile["id"], internship_id)))
            is_saved = bool(db.query_one(
                conn, "SELECT id FROM saved_internships WHERE student_id = ? "
                      "AND internship_id = ?", (profile["id"], internship_id)))

    applicant_count = db.query_one(
        conn, "SELECT COUNT(*) AS n FROM applications WHERE internship_id = ?",
        (internship_id,))["n"]

    return render_template(
        "internship_detail.html", internship=internship, skills=skills, match=match,
        profile=profile, already_applied=already_applied, is_saved=is_saved,
        courses=courses, applicant_count=applicant_count,
    )


@app.route("/internship/<int:internship_id>/apply", methods=["POST"])
@role_required("student")
def apply_internship(internship_id):
    conn = get_db()
    profile = student_profile_or_404()
    internship = db.query_one(
        conn, "SELECT * FROM internships WHERE id = ? AND is_active = 1", (internship_id,))
    if not internship:
        flash("That internship is no longer accepting applications.", "danger")
        return redirect(url_for("internships"))

    student_skills = db.student_skill_names(conn, profile["id"])
    if not student_skills:
        flash("Add your skills first so companies can see why you match.", "warning")
        return redirect(url_for("student_skills"))

    match = score_match(profile, internship, student_skills,
                        db.internship_skill_map(conn, internship_id))
    created = save_application(conn, profile["id"], internship_id, match["score_exact"])
    if created:
        flash(f"Applied to {internship['title']} with a {match['score']}% match.", "success")
    else:
        flash("You have already applied to this internship.", "info")
    return redirect(url_for("internship_detail", internship_id=internship_id))


@app.route("/internship/<int:internship_id>/save", methods=["POST"])
@role_required("student")
def save_internship(internship_id):
    conn = get_db()
    profile = student_profile_or_404()
    if not db.query_one(conn, "SELECT id FROM internships WHERE id = ?", (internship_id,)):
        abort(404, "That internship does not exist.")
    existing = db.query_one(
        conn, "SELECT id FROM saved_internships WHERE student_id = ? AND internship_id = ?",
        (profile["id"], internship_id))
    if existing:
        db.execute(conn, "DELETE FROM saved_internships WHERE id = ?", (existing["id"],))
        flash("Removed from your saved list.", "info")
    else:
        db.execute(
            conn, "INSERT INTO saved_internships (student_id, internship_id) VALUES (?, ?)",
            (profile["id"], internship_id))
        flash("Saved for later.", "success")
    return redirect(request.referrer or url_for("internships"))


# ===========================================================================
# COMPANY / INDUSTRY
# ===========================================================================

@app.route("/company/dashboard")
@role_required("company")
def company_dashboard():
    conn = get_db()
    company = company_or_404()

    internships_rows = db.query_all(
        conn,
        """SELECT i.*, (SELECT COUNT(*) FROM applications a WHERE a.internship_id = i.id)
                  AS applicant_count
           FROM internships i WHERE i.company_id = ?
           ORDER BY i.created_at DESC, i.id DESC""",
        (company["id"],),
    )
    applications = db.query_all(
        conn,
        """SELECT a.*, i.title, u.name AS student_name, sp.branch, sp.qualification,
                  sp.preferred_location
           FROM applications a
           JOIN internships i      ON i.id = a.internship_id
           JOIN student_profiles sp ON sp.id = a.student_id
           JOIN users u            ON u.id = sp.user_id
           WHERE i.company_id = ?
           ORDER BY a.applied_at DESC, a.id DESC LIMIT 6""",
        (company["id"],),
    )

    # Top candidates across this company's most recent active internship.
    newest = db.query_one(
        conn,
        """SELECT * FROM internships WHERE company_id = ? AND is_active = 1
           ORDER BY created_at DESC, id DESC LIMIT 1""",
        (company["id"],),
    )
    top_candidates = rank_candidates(conn, newest, limit=5) if newest else []

    totals = {
        "internships": len(internships_rows),
        "active": sum(1 for r in internships_rows if r["is_active"]),
        "openings": sum(r["openings"] or 0 for r in internships_rows),
        "applications": db.query_one(
            conn,
            """SELECT COUNT(*) AS n FROM applications a JOIN internships i
               ON i.id = a.internship_id WHERE i.company_id = ?""",
            (company["id"],))["n"],
        "shortlisted": db.query_one(
            conn,
            """SELECT COUNT(*) AS n FROM applications a JOIN internships i
               ON i.id = a.internship_id WHERE i.company_id = ? AND a.status = 'Shortlisted'""",
            (company["id"],))["n"],
    }

    return render_template(
        "industry_dashboard.html", company=company, internships=internships_rows[:5],
        applications=applications, top_candidates=top_candidates,
        newest=newest, totals=totals,
        requested_skills=analytics.top_requested_skills_for_company(conn, company["id"]),
        talent_pool=analytics.counts(conn)["students_with_skills"],
    )


@app.route("/company/profile", methods=["GET", "POST"])
@role_required("company")
def company_profile():
    conn = get_db()
    company = company_or_404()
    if request.method == "POST":
        name = clean_text(request.form.get("company_name"), 120)
        if len(name) < 2:
            flash("Company name is required.", "danger")
            return redirect(url_for("company_profile"))
        db.execute(
            conn,
            """UPDATE companies SET company_name = ?, industry = ?, website = ?,
                 location = ?, about = ? WHERE id = ?""",
            (name, clean_text(request.form.get("industry"), 80),
             clean_text(request.form.get("website"), 200),
             clean_text(request.form.get("location"), 60),
             clean_block(request.form.get("about"), 1500), company["id"]),
        )
        flash("Company profile saved.", "success")
        return redirect(url_for("company_profile"))
    return render_template("company_profile.html", company=company)


@app.route("/company/post-internship", methods=["GET", "POST"])
@role_required("company")
def post_internship():
    conn = get_db()
    company = company_or_404()

    if request.method == "POST":
        title = clean_text(request.form.get("title"), 120)
        location = clean_text(request.form.get("location"), 60)
        required = split_skills(request.form.get("required_skills"))
        preferred = split_skills(request.form.get("preferred_skills"))
        stipend_min = to_int(request.form.get("stipend_min"), 0, 0, 500000)
        stipend_max = to_int(request.form.get("stipend_max"), 0, 0, 500000)
        if stipend_max and stipend_min > stipend_max:
            stipend_min, stipend_max = stipend_max, stipend_min

        errors = []
        if len(title) < 3:
            errors.append("Please enter an internship title.")
        if not location:
            errors.append("Please enter a location (or type Remote).")
        if not required:
            errors.append("Please list at least one required skill.")
        if errors:
            for message in errors:
                flash(message, "danger")
            return render_template("post_internship.html", company=company,
                                   form=request.form,
                                   all_skills=rp.all_skill_names(),
                                   options=filter_options()), 400

        cursor = db.execute(
            conn,
            """INSERT INTO internships
                 (company_id, title, description, domain, location, stipend_min,
                  stipend_max, duration_months, qualification, openings, is_active, is_demo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)""",
            (company["id"], title,
             clean_block(request.form.get("description"), 4000),
             clean_text(request.form.get("domain"), 60) or "General",
             location, stipend_min, stipend_max,
             to_int(request.form.get("duration_months"), 3, 1, 24),
             clean_text(request.form.get("qualification"), 120) or "Any Degree",
             to_int(request.form.get("openings"), 1, 1, 500)),
        )
        internship_id = cursor.lastrowid

        for importance, names in (("required", required), ("preferred", preferred)):
            for name in names:
                skill_id = db.get_or_create_skill(conn, name, rp.skill_category(name))
                db.execute(
                    conn,
                    """INSERT OR IGNORE INTO internship_skills
                       (internship_id, skill_id, importance) VALUES (?, ?, ?)""",
                    (internship_id, skill_id, importance),
                )

        flash(f"'{title}' is live. Here are the students who match it best.", "success")
        return redirect(url_for("company_candidates", internship_id=internship_id))

    return render_template("post_internship.html", company=company, form={},
                           all_skills=rp.all_skill_names(), options=filter_options())


@app.route("/company/internships")
@role_required("company")
def company_internships():
    conn = get_db()
    company = company_or_404()
    rows = db.query_all(
        conn,
        """SELECT i.*,
                  (SELECT COUNT(*) FROM applications a WHERE a.internship_id = i.id)
                    AS applicant_count,
                  (SELECT COUNT(*) FROM applications a WHERE a.internship_id = i.id
                     AND a.status = 'Shortlisted') AS shortlisted_count
           FROM internships i WHERE i.company_id = ?
           ORDER BY i.is_active DESC, i.created_at DESC, i.id DESC""",
        (company["id"],),
    )
    skills_map = db.all_internship_skills(conn)
    return render_template("company_internships.html", company=company, internships=rows,
                           skills_map=skills_map)


@app.route("/company/internship/<int:internship_id>/toggle", methods=["POST"])
@role_required("company")
def toggle_internship(internship_id):
    conn = get_db()
    company = company_or_404()
    internship = db.query_one(
        conn, "SELECT * FROM internships WHERE id = ? AND company_id = ?",
        (internship_id, company["id"]))
    if not internship:
        abort(403, "That internship does not belong to your company.")
    new_state = 0 if internship["is_active"] else 1
    db.execute(conn, "UPDATE internships SET is_active = ? WHERE id = ?",
               (new_state, internship_id))
    flash("Internship " + ("reopened." if new_state else "closed."), "info")
    return redirect(url_for("company_internships"))


@app.route("/company/candidates")
@app.route("/company/candidates/<int:internship_id>")
@role_required("company")
def company_candidates(internship_id=None):
    """Ranked students for one of this company's internships."""
    conn = get_db()
    company = company_or_404()

    postings = db.query_all(
        conn,
        "SELECT id, title, location FROM internships WHERE company_id = ? "
        "ORDER BY is_active DESC, id DESC",
        (company["id"],),
    )
    if not postings:
        flash("Post an internship first, then we can rank students for it.", "info")
        return redirect(url_for("post_internship"))

    if internship_id is None:
        internship_id = postings[0]["id"]

    internship = db.query_one(
        conn, "SELECT * FROM internships WHERE id = ? AND company_id = ?",
        (internship_id, company["id"]))
    if not internship:
        abort(403, "That internship does not belong to your company.")

    sort_by = read_sort()
    candidates = rank_candidates(conn, internship, limit=25, sort_by=sort_by)
    return render_template(
        "candidates.html", company=company, internship=internship, postings=postings,
        candidates=candidates, skills=db.internship_skill_map(conn, internship_id),
        sort_by=sort_by, sort_options=SORT_OPTIONS,
    )


@app.route("/company/applications")
@role_required("company")
def company_applications():
    conn = get_db()
    company = company_or_404()
    status_filter = clean_text(request.args.get("status"), 20)

    sql = """SELECT a.*, i.title, i.location, u.name AS student_name, u.email,
                    sp.branch, sp.qualification, sp.graduation_year, sp.college,
                    sp.preferred_location, sp.id AS student_profile_id
             FROM applications a
             JOIN internships i       ON i.id = a.internship_id
             JOIN student_profiles sp ON sp.id = a.student_id
             JOIN users u             ON u.id = sp.user_id
             WHERE i.company_id = ?"""
    params = [company["id"]]
    if status_filter in APPLICATION_STATUSES:
        sql += " AND a.status = ?"
        params.append(status_filter)
    sql += " ORDER BY a.applied_at DESC, a.id DESC"

    rows = db.query_all(conn, sql, tuple(params))
    # Attach each applicant's skills so the company sees why they matched.
    enriched = []
    for row in rows:
        enriched.append({
            "application": row,
            "skills": db.student_skill_names(conn, row["student_profile_id"]),
        })
    return render_template("company_applications.html", company=company,
                           applications=enriched, status_filter=status_filter)


@app.route("/company/application/<int:application_id>/status", methods=["POST"])
@role_required("company")
def update_application_status(application_id):
    conn = get_db()
    company = company_or_404()
    row = db.query_one(
        conn,
        """SELECT a.id FROM applications a JOIN internships i ON i.id = a.internship_id
           WHERE a.id = ? AND i.company_id = ?""",
        (application_id, company["id"]),
    )
    if not row:
        abort(403, "That application is not for one of your internships.")

    new_status = clean_text(request.form.get("status"), 20)
    if new_status not in APPLICATION_STATUSES:
        flash("Unknown application status.", "danger")
        return redirect(url_for("company_applications"))

    db.execute(conn, "UPDATE applications SET status = ? WHERE id = ?",
               (new_status, application_id))
    flash(f"Application marked as {new_status}.", "success")
    return redirect(request.referrer or url_for("company_applications"))


# ===========================================================================
# ACADEMIA / COLLEGE
# ===========================================================================

@app.route("/academia/dashboard")
@role_required("academia")
def academia_dashboard():
    conn = get_db()
    institution = db.query_one(
        conn, "SELECT * FROM academia WHERE user_id = ?", (session["user_id"],))
    return render_template(
        "academia_dashboard.html",
        institution=institution,
        stats=analytics.counts(conn),
        comparison=analytics.demand_vs_supply(conn, 10),
        gaps=analytics.biggest_gaps(conn, 8),
        common_gaps=analytics.common_student_gaps(conn, 8),
        domains=analytics.popular_domains(conn),
        locations=analytics.location_spread(conn),
        placement=analytics.placement_stats(conn),
    )


@app.route("/academia/skill-demand")
@role_required("academia")
def academia_skill_demand():
    conn = get_db()
    return render_template(
        "skill_demand.html",
        stats=analytics.counts(conn),
        demand=analytics.industry_skill_demand(conn, 20),
        supply=analytics.student_skill_supply(conn, 20),
        comparison=analytics.demand_vs_supply(conn, 15),
        gaps=analytics.biggest_gaps(conn, 12),
        common_gaps=analytics.common_student_gaps(conn, 12),
    )


# ===========================================================================
# SMALL JSON API (used by the front-end JavaScript)
# ===========================================================================

@app.route("/api/skills")
def api_skills():
    """Autocomplete source for the skill input boxes."""
    term = clean_text(request.args.get("q"), 40).lower()
    names = rp.all_skill_names()
    if term:
        names = [n for n in names if term in n.lower()]
    return jsonify(names[:25])


@app.route("/api/internships")
def api_internships():
    """JSON version of the listing - handy for debugging the filters."""
    conn = get_db()
    rows = load_internships(conn, read_filters())
    skills_map = db.all_internship_skills(conn)
    return jsonify([{
        "id": r["id"], "title": r["title"], "company": r["company_name"],
        "location": r["location"], "domain": r["domain"],
        "stipend_min": r["stipend_min"], "stipend_max": r["stipend_max"],
        "duration_months": r["duration_months"],
        "required_skills": skills_map.get(r["id"], {}).get("required", []),
        "preferred_skills": skills_map.get(r["id"], {}).get("preferred", []),
    } for r in rows])


# ===========================================================================
# ERROR HANDLERS  (friendly message, never a stack trace)
# ===========================================================================

@app.errorhandler(403)
def error_403(error):
    return render_template("error.html", code=403, title="Not allowed",
                           message=getattr(error, "description",
                                           "You do not have access to that page.")), 403


@app.errorhandler(404)
def error_404(error):
    return render_template("error.html", code=404, title="Page not found",
                           message=getattr(error, "description",
                                           "We could not find that page.")), 404


@app.errorhandler(413)
def error_413(_error):
    return render_template(
        "error.html", code=413, title="File too large",
        message=f"Resumes must be smaller than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."), 413


@app.errorhandler(500)
def error_500(_error):
    # Log the real problem to the terminal, show the user something safe.
    app.logger.exception("Unhandled server error")
    return render_template(
        "error.html", code=500, title="Something went wrong",
        message="An unexpected error occurred. Please try again."), 500


# ===========================================================================
# STARTUP
# ===========================================================================

def ensure_database():
    """Fail with a clear instruction instead of a stack trace on a fresh clone."""
    if not os.path.exists(db.DB_PATH):
        print("\n  No database found at", db.DB_PATH)
        print("  Run this first:   python init_db.py\n")
        return False
    return True


if __name__ == "__main__":
    if not ensure_database():
        sys.exit(1)

    port = 5000
    if "--port" in sys.argv:
        try:
            port = int(sys.argv[sys.argv.index("--port") + 1])
        except (IndexError, ValueError):
            print("  --port needs a number, e.g. python app.py --port 5001")
            sys.exit(1)

    print("\n  SkillBridge is starting ...")
    print(f"  Open http://127.0.0.1:{port} in your browser")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, port=port)
