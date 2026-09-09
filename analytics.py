"""
analytics.py
============
The aggregate queries behind the ACADEMIA dashboard.

Every number here is a live SQL aggregate over the same tables the students and
companies write to - nothing is hardcoded. The two headline series are:

  industry demand    = % of active internships that ask for a skill
  student supply     = % of students with a profile who actually have that skill
  gap                = demand - supply   (positive = the college should teach it)
"""

from database import query_all, query_one


def _percent(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0.0


def counts(conn):
    """Small numbers for the stat tiles."""
    def one(sql, params=()):
        row = query_one(conn, sql, params)
        return row["n"] if row else 0

    return {
        "students": one("SELECT COUNT(*) AS n FROM student_profiles"),
        "students_with_skills": one(
            "SELECT COUNT(DISTINCT student_id) AS n FROM student_skills"),
        "students_with_resume": one(
            "SELECT COUNT(*) AS n FROM student_profiles WHERE resume_text IS NOT NULL "
            "AND resume_text != ''"),
        "companies": one("SELECT COUNT(*) AS n FROM companies"),
        "internships": one("SELECT COUNT(*) AS n FROM internships WHERE is_active = 1"),
        "openings": one("SELECT COALESCE(SUM(openings), 0) AS n FROM internships "
                        "WHERE is_active = 1"),
        "applications": one("SELECT COUNT(*) AS n FROM applications"),
        "applicants": one("SELECT COUNT(DISTINCT student_id) AS n FROM applications"),
        "shortlisted": one("SELECT COUNT(*) AS n FROM applications "
                           "WHERE status = 'Shortlisted'"),
        "selected": one("SELECT COUNT(*) AS n FROM applications WHERE status = 'Selected'"),
        "skills_tracked": one("SELECT COUNT(*) AS n FROM skills"),
        "courses": one("SELECT COUNT(*) AS n FROM courses"),
    }


def industry_skill_demand(conn, limit=12):
    """
    How often each skill is asked for across active internships.
    A required skill counts fully; a preferred skill counts too (both are demand).
    """
    total = query_one(conn, "SELECT COUNT(*) AS n FROM internships WHERE is_active = 1")
    total = total["n"] if total else 0
    rows = query_all(
        conn,
        """SELECT s.name, s.category,
                  COUNT(DISTINCT i.id) AS n_internships,
                  SUM(CASE WHEN isk.importance = 'required' THEN 1 ELSE 0 END) AS n_required
           FROM internship_skills isk
           JOIN skills s      ON s.id = isk.skill_id
           JOIN internships i ON i.id = isk.internship_id AND i.is_active = 1
           GROUP BY s.id
           ORDER BY n_internships DESC, s.name
           LIMIT ?""",
        (limit,),
    )
    return [
        {
            "skill": r["name"],
            "category": r["category"],
            "count": r["n_internships"],
            "required_count": r["n_required"],
            "percent": _percent(r["n_internships"], total),
        }
        for r in rows
    ]


def student_skill_supply(conn, limit=12):
    """How many students actually have each skill."""
    total = query_one(conn, "SELECT COUNT(*) AS n FROM student_profiles")
    total = total["n"] if total else 0
    rows = query_all(
        conn,
        """SELECT s.name, s.category, COUNT(DISTINCT ss.student_id) AS n_students
           FROM student_skills ss
           JOIN skills s ON s.id = ss.skill_id
           GROUP BY s.id
           ORDER BY n_students DESC, s.name
           LIMIT ?""",
        (limit,),
    )
    return [
        {
            "skill": r["name"],
            "category": r["category"],
            "count": r["n_students"],
            "percent": _percent(r["n_students"], total),
        }
        for r in rows
    ]


def demand_vs_supply(conn, limit=10):
    """
    The main academia chart: for the most in-demand skills, industry demand %
    next to student availability %, plus the gap between them.
    """
    total_internships = query_one(
        conn, "SELECT COUNT(*) AS n FROM internships WHERE is_active = 1")
    total_internships = total_internships["n"] if total_internships else 0
    total_students = query_one(conn, "SELECT COUNT(*) AS n FROM student_profiles")
    total_students = total_students["n"] if total_students else 0

    rows = query_all(
        conn,
        """SELECT s.id, s.name, s.category,
                  (SELECT COUNT(DISTINCT isk.internship_id)
                     FROM internship_skills isk
                     JOIN internships i ON i.id = isk.internship_id AND i.is_active = 1
                    WHERE isk.skill_id = s.id) AS demand_count,
                  (SELECT COUNT(DISTINCT ss.student_id)
                     FROM student_skills ss
                    WHERE ss.skill_id = s.id) AS supply_count
           FROM skills s
           ORDER BY demand_count DESC, s.name
           LIMIT ?""",
        (limit,),
    )

    result = []
    for row in rows:
        if not row["demand_count"]:
            continue
        demand = _percent(row["demand_count"], total_internships)
        supply = _percent(row["supply_count"], total_students)
        gap = round(demand - supply, 1)
        result.append({
            "skill": row["name"],
            "category": row["category"],
            "demand_percent": demand,
            "supply_percent": supply,
            "demand_count": row["demand_count"],
            "supply_count": row["supply_count"],
            "gap": gap,
            "severity": _severity(gap),
        })
    return result


def biggest_gaps(conn, limit=8, min_gap=5):
    """
    Same data as demand_vs_supply, re-sorted so the skills the college should act
    on come first (industry wants it much more than students have it).
    """
    rows = [r for r in demand_vs_supply(conn, limit=200) if r["gap"] >= min_gap]
    rows.sort(key=lambda r: r["gap"], reverse=True)
    return rows[:limit]


def _severity(gap):
    """Traffic light for a demand-supply gap (used with an icon + label, never colour alone)."""
    if gap >= 40:
        return "critical"
    if gap >= 25:
        return "serious"
    if gap >= 10:
        return "warning"
    return "good"


def common_student_gaps(conn, limit=10):
    """
    Aggregate of the `skill_gaps` table: which skills are missing for the most
    students, according to the recommendations the engine actually produced.
    """
    total_students = query_one(
        conn, "SELECT COUNT(DISTINCT student_id) AS n FROM skill_gaps")
    total_students = total_students["n"] if total_students else 0
    rows = query_all(
        conn,
        """SELECT s.name, s.category,
                  COUNT(DISTINCT g.student_id) AS n_students,
                  SUM(g.demand_count) AS total_demand
           FROM skill_gaps g
           JOIN skills s ON s.id = g.skill_id
           GROUP BY s.id
           ORDER BY n_students DESC, total_demand DESC, s.name
           LIMIT ?""",
        (limit,),
    )
    return [
        {
            "skill": r["name"],
            "category": r["category"],
            "students_missing": r["n_students"],
            "percent": _percent(r["n_students"], total_students),
            "internship_mentions": r["total_demand"],
        }
        for r in rows
    ]


def popular_domains(conn):
    """Internship count and applications per domain."""
    rows = query_all(
        conn,
        """SELECT i.domain,
                  COUNT(DISTINCT i.id) AS n_internships,
                  COALESCE(SUM(i.openings), 0) AS n_openings,
                  (SELECT COUNT(*) FROM applications a
                    JOIN internships i2 ON i2.id = a.internship_id
                   WHERE i2.domain = i.domain) AS n_applications,
                  CAST(AVG(MAX(i.stipend_min, i.stipend_max)) AS INTEGER) AS avg_stipend
           FROM internships i
           WHERE i.is_active = 1
           GROUP BY i.domain
           ORDER BY n_internships DESC, i.domain""",
    )
    return [dict(r) for r in rows]


def location_spread(conn):
    """Internships per city - shows where the opportunities actually are."""
    rows = query_all(
        conn,
        """SELECT location, COUNT(*) AS n_internships,
                  CAST(AVG(MAX(stipend_min, stipend_max)) AS INTEGER) AS avg_stipend
           FROM internships WHERE is_active = 1
           GROUP BY location ORDER BY n_internships DESC, location""",
    )
    return [dict(r) for r in rows]


def placement_stats(conn):
    """
    Placement-style funnel + per-branch table.
    'Placed' here means an application reached status 'Selected'.
    """
    base = counts(conn)
    funnel = [
        {"stage": "Students registered", "value": base["students"]},
        {"stage": "Skill profile created", "value": base["students_with_skills"]},
        {"stage": "Applied to internships", "value": base["applicants"]},
        {"stage": "Shortlisted", "value": base["shortlisted"]},
        {"stage": "Selected", "value": base["selected"]},
    ]
    top = funnel[0]["value"] or 1
    for stage in funnel:
        stage["percent"] = _percent(stage["value"], top)

    by_branch = query_all(
        conn,
        """SELECT COALESCE(NULLIF(sp.branch, ''), 'Not set') AS branch,
                  COUNT(DISTINCT sp.id) AS students,
                  COUNT(DISTINCT a.student_id) AS applied,
                  SUM(CASE WHEN a.status = 'Selected' THEN 1 ELSE 0 END) AS selected,
                  SUM(CASE WHEN a.status = 'Shortlisted' THEN 1 ELSE 0 END) AS shortlisted
           FROM student_profiles sp
           LEFT JOIN applications a ON a.student_id = sp.id
           GROUP BY branch
           ORDER BY students DESC, branch""",
    )
    branches = []
    for row in by_branch:
        entry = dict(row)
        entry["participation"] = _percent(entry["applied"], entry["students"])
        branches.append(entry)

    return {
        "funnel": funnel,
        "by_branch": branches,
        "application_status": [
            dict(r) for r in query_all(
                conn,
                """SELECT status, COUNT(*) AS n FROM applications
                   GROUP BY status ORDER BY n DESC""")
        ],
        "avg_match_score": (lambda r: round(r["avg"], 1) if r and r["avg"] else 0.0)(
            query_one(conn, "SELECT AVG(match_score) AS avg FROM applications")
        ),
    }


def top_requested_skills_for_company(conn, company_id, limit=8):
    """'Most requested skills' tile on the industry dashboard."""
    rows = query_all(
        conn,
        """SELECT s.name, COUNT(*) AS n
           FROM internship_skills isk
           JOIN skills s ON s.id = isk.skill_id
           JOIN internships i ON i.id = isk.internship_id
           WHERE i.company_id = ?
           GROUP BY s.id ORDER BY n DESC, s.name LIMIT ?""",
        (company_id, limit),
    )
    return [dict(r) for r in rows]
