"""
recommendation.py
=================
The explainable matching engine. Nothing here is hardcoded - every number comes
out of the database rows that are passed in.

THE FORMULA
-----------
    final = 50% skills + 20% qualification + 15% location + 10% stipend + 5% experience

Each of the five parts returns a 0.0 - 1.0 sub-score plus a human sentence
("Location matches (Hyderabad)"), so a student can always see WHY they got 91%.

An OPTIONAL machine-learning layer (ml/model.py) sits on top. It takes the same
five sub-scores and predicts P(shortlisted), which is used ONLY as the sort key:

    rank_score = 70% rule score + 30% ML shortlist probability

The number the user SEES ("91% Match") is always the rule score, so the displayed
percentage is exactly the sum of the five weighted rows in the breakdown table.
The ML probability is shown beside it as a separate "shortlist likelihood" chip.

TWO SORT ORDERS (this matters - see `sort_results`)
  sort_by="match"  (default) - order by the rule score, ML only breaks ties.
                               The list therefore always reads top-to-bottom in
                               descending percentage, which is what a user expects.
  sort_by="ml"               - order by rank_score, i.e. let the model re-rank.
                               Offered as an explicit, labelled toggle in the UI.

Sorting by the blended key while displaying the rule score would show a 74% above
a 77% and look like a bug, so the re-ranking is never silent - the user chooses it.

If scikit-learn is not installed everything still works: `ml_score` is None, the
toggle falls back to the rule score, and nothing else changes.
"""

import resume_parser as rp
from database import all_internship_skills, internship_skill_map, query_all, query_one

# ---------------------------------------------------------------------------
# Weights - change these in ONE place
# ---------------------------------------------------------------------------
WEIGHTS = {
    "skills": 0.50,
    "qualification": 0.20,
    "location": 0.15,
    "stipend": 0.10,
    "experience": 0.05,
}

PART_LABELS = {
    "skills": "Skill match",
    "qualification": "Qualification",
    "location": "Location",
    "stipend": "Stipend",
    "experience": "Experience & projects",
}

# How much of the ML probability is mixed into the RANKING key (not the shown score).
ML_BLEND = 0.30

# A preferred (nice-to-have) skill is worth half a required skill.
PREFERRED_WEIGHT = 0.5

# Cities close enough to count as a partial location match.
CITY_CLUSTERS = [
    {"hyderabad", "secunderabad", "hitech city", "telangana"},
    {"bangalore", "bengaluru", "karnataka"},
    {"delhi", "new delhi", "noida", "gurgaon", "gurugram", "ncr", "faridabad"},
    {"mumbai", "navi mumbai", "thane", "pune", "maharashtra"},
    {"chennai", "coimbatore", "tamil nadu"},
    {"kolkata", "west bengal"},
    {"ahmedabad", "gandhinagar", "gujarat"},
]


def _clean(value):
    return (str(value).strip().lower()) if value else ""


def _same_cluster(a, b):
    for cluster in CITY_CLUSTERS:
        if any(city in a for city in cluster) and any(city in b for city in cluster):
            return True
    return False


# ---------------------------------------------------------------------------
# 1. SKILLS  (50%)
# ---------------------------------------------------------------------------

def score_skills(student_skills, required, preferred):
    """
    Weighted coverage of the internship's skill list.
        score = (matched required + 0.5 x matched preferred)
                / (all required + 0.5 x all preferred)
    """
    have = {s.lower() for s in student_skills}
    required = required or []
    preferred = preferred or []

    matched_req = [s for s in required if s.lower() in have]
    missing_req = [s for s in required if s.lower() not in have]
    matched_pref = [s for s in preferred if s.lower() in have]
    missing_pref = [s for s in preferred if s.lower() not in have]

    total = len(required) + PREFERRED_WEIGHT * len(preferred)
    if total == 0:
        # The company listed no skills - stay neutral instead of giving 0 or 100.
        return 0.6, {
            "matched_required": [], "missing_required": [],
            "matched_preferred": [], "missing_preferred": [],
            "detail": "No specific skills listed by the company",
        }

    got = len(matched_req) + PREFERRED_WEIGHT * len(matched_pref)
    score = got / total
    detail = f"{len(matched_req)} of {len(required)} required skills matched" if required \
        else f"{len(matched_pref)} of {len(preferred)} preferred skills matched"
    return score, {
        "matched_required": matched_req, "missing_required": missing_req,
        "matched_preferred": matched_pref, "missing_preferred": missing_pref,
        "detail": detail,
    }


# ---------------------------------------------------------------------------
# 2. QUALIFICATION  (20%)
# ---------------------------------------------------------------------------

def score_qualification(student_degree, student_branch, internship_qualification):
    """
    Degree is worth 65% of this part, branch 35%.
    'Any Degree' / an empty requirement is treated as open to everyone.
    """
    wanted = internship_qualification or ""
    lowered = _clean(wanted)
    open_to_all = (not lowered) or "any degree" in lowered or "any graduate" in lowered \
        or lowered in ("any", "all", "open")

    if open_to_all:
        return 1.0, "Open to all degrees"

    degrees = rp.find_all_aliases(wanted, rp.DEGREE_ALIASES)
    branches = rp.find_all_aliases(wanted, rp.BRANCH_ALIASES)
    any_branch = "any branch" in lowered or "all branches" in lowered

    my_degree = (student_degree or "").strip()
    my_branch = (student_branch or "").strip()

    # ---- degree ----
    if not degrees:
        degree_part, degree_note = 1.0, "no specific degree required"
    elif my_degree in degrees:
        degree_part, degree_note = 1.0, f"degree matches ({my_degree})"
    elif rp.DEGREE_FAMILIES.get(my_degree, set()) & degrees:
        degree_part, degree_note = 0.75, f"{my_degree} is an accepted equivalent"
    elif not my_degree:
        degree_part, degree_note = 0.3, "your degree is not filled in"
    else:
        degree_part, degree_note = 0.0, f"asks for {'/'.join(sorted(degrees))}"

    # ---- branch ----
    if any_branch or not branches:
        branch_part, branch_note = 1.0, "any branch"
    elif my_branch in branches:
        branch_part, branch_note = 1.0, f"branch matches ({my_branch})"
    elif not my_branch:
        branch_part, branch_note = 0.3, "your branch is not filled in"
    else:
        branch_part, branch_note = 0.0, f"prefers {'/'.join(sorted(branches))}"

    score = 0.65 * degree_part + 0.35 * branch_part
    score = max(score, 0.2)  # never a hard zero - companies do flex on this
    detail = f"{degree_note}, {branch_note}"
    # Upper-case only the first letter - .capitalize() would turn "B.Tech" into "b.tech".
    return score, detail[0].upper() + detail[1:]


# ---------------------------------------------------------------------------
# 3. LOCATION  (15%)
# ---------------------------------------------------------------------------

def score_location(preferred_location, internship_location):
    mine = _clean(preferred_location)
    theirs = _clean(internship_location)

    if not mine:
        return 1.0, "No location preference set"
    if not theirs:
        return 0.5, "Location not specified by the company"
    if "remote" in theirs or "work from home" in theirs:
        return 1.0, "Remote - works with any preference"
    if mine in ("any", "anywhere", "any location"):
        return 1.0, "You are open to any location"
    if "remote" in mine:
        return 0.3, f"On-site in {internship_location}, you prefer Remote"
    if mine == theirs or mine in theirs or theirs in mine:
        return 1.0, f"Location matches ({internship_location})"
    if _same_cluster(mine, theirs):
        return 0.85, f"{internship_location} is near your preferred {preferred_location}"
    return 0.25, f"{internship_location} vs your preferred {preferred_location}"


# ---------------------------------------------------------------------------
# 4. STIPEND  (10%)
# ---------------------------------------------------------------------------

def score_stipend(min_expected, max_expected, offer_min, offer_max):
    min_expected = int(min_expected or 0)
    max_expected = int(max_expected or 0)
    offer_min = int(offer_min or 0)
    offer_max = int(offer_max or 0)
    best_offer = max(offer_min, offer_max)

    if not min_expected and not max_expected:
        return 1.0, "No stipend expectation set"
    if not best_offer:
        return 0.4, "Stipend not disclosed"
    if best_offer >= min_expected:
        if max_expected and best_offer > max_expected:
            return 1.0, f"Pays Rs {best_offer:,}/month - above your range"
        return 1.0, f"Pays Rs {best_offer:,}/month - inside your range"
    # Pays less than the student asked for: partial credit, proportional to the shortfall.
    ratio = best_offer / min_expected
    return max(0.1, round(ratio, 3)), \
        f"Pays Rs {best_offer:,}/month, you expect at least Rs {min_expected:,}"


# ---------------------------------------------------------------------------
# 5. EXPERIENCE & PROJECT RELEVANCE  (5%)
# ---------------------------------------------------------------------------

def score_experience(experience_months, projects_text, internship, skills_needed):
    """
    40% prior experience (6 months = full marks),
    60% project relevance (do the projects mention the skills / domain asked for?).
    """
    months = int(experience_months or 0)
    exp_part = min(months / 6.0, 1.0)

    text = _clean(projects_text)
    hits = []
    if text:
        haystack = text
        for skill in skills_needed:
            if skill.lower() in haystack:
                hits.append(skill)
        for word in (internship.get("domain") or "").lower().split():
            if len(word) > 3 and word in haystack and word not in [h.lower() for h in hits]:
                hits.append(word.title())
    project_part = min(len(hits) / 2.0, 1.0)

    score = 0.4 * exp_part + 0.6 * project_part
    bits = []
    if months:
        bits.append(f"{months} month(s) experience")
    if hits:
        bits.append("projects mention " + ", ".join(hits[:3]))
    detail = "; ".join(bits) if bits else "No experience or project details yet"
    return score, detail


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------

def _as_dict(row):
    """Accept sqlite3.Row or plain dict everywhere."""
    return row if isinstance(row, dict) else dict(row)


def score_match(student, internship, student_skills, skills=None, use_ml=True):
    """
    Score ONE student against ONE internship.

    student      : student_profiles row (or dict)
    internship   : internships row (or dict)
    student_skills: list of canonical skill names the student has
    skills       : {'required': [...], 'preferred': [...]} for this internship
    """
    student = _as_dict(student)
    internship = _as_dict(internship)
    skills = skills or {"required": [], "preferred": []}
    required = skills.get("required", [])
    preferred = skills.get("preferred", [])

    skill_score, skill_detail = score_skills(student_skills, required, preferred)
    qual_score, qual_detail = score_qualification(
        student.get("qualification"), student.get("branch"), internship.get("qualification")
    )
    loc_score, loc_detail = score_location(
        student.get("preferred_location"), internship.get("location")
    )
    stip_score, stip_detail = score_stipend(
        student.get("min_stipend"), student.get("max_stipend"),
        internship.get("stipend_min"), internship.get("stipend_max"),
    )
    exp_score, exp_detail = score_experience(
        student.get("experience_months"), student.get("projects_text"),
        internship, required + preferred,
    )

    sub_scores = {
        "skills": skill_score,
        "qualification": qual_score,
        "location": loc_score,
        "stipend": stip_score,
        "experience": exp_score,
    }
    details = {
        "skills": skill_detail["detail"],
        "qualification": qual_detail,
        "location": loc_detail,
        "stipend": stip_detail,
        "experience": exp_detail,
    }

    rule_fraction = sum(WEIGHTS[k] * v for k, v in sub_scores.items())
    rule_score = round(rule_fraction * 100, 1)

    # ---- optional ML re-ranking layer ----
    ml_score = None
    features = build_features(sub_scores)
    if use_ml:
        from ml.model import predict_probability
        probability = predict_probability(features)
        if probability is not None:
            ml_score = round(probability * 100, 1)

    # The displayed score is ALWAYS the rule score (it must equal the breakdown
    # total). The ML probability only shifts the sort order.
    if ml_score is None:
        rank_score = rule_score
    else:
        rank_score = round((1 - ML_BLEND) * rule_score + ML_BLEND * ml_score, 2)

    breakdown = []
    for key, weight in WEIGHTS.items():
        breakdown.append({
            "key": key,
            "label": PART_LABELS[key],
            "weight": int(weight * 100),
            "score": round(sub_scores[key], 3),
            "percent": round(sub_scores[key] * 100),
            "points": round(weight * sub_scores[key] * 100, 1),
            "detail": details[key],
            "ok": sub_scores[key] >= 0.75,
        })

    return {
        "score": int(round(rule_score)),          # <- shown in the UI
        "score_exact": rule_score,
        "rule_score": rule_score,
        "ml_score": ml_score,                     # P(shortlisted) as a %, or None
        "rank_score": rank_score,                 # <- used for sorting only
        "sub_scores": sub_scores,
        "breakdown": breakdown,
        "features": features,
        "matched_skills": skill_detail["matched_required"] + skill_detail["matched_preferred"],
        "missing_skills": skill_detail["missing_required"] + skill_detail["missing_preferred"],
        "matched_required": skill_detail["matched_required"],
        "missing_required": skill_detail["missing_required"],
        "matched_preferred": skill_detail["matched_preferred"],
        "missing_preferred": skill_detail["missing_preferred"],
        "required_skills": required,
        "preferred_skills": preferred,
    }


def build_features(sub_scores):
    """
    The 7 numbers handed to the ML model.
    The last two are engineered: recruiters do not shortlist a great skill match
    that is in an impossible city (interaction), and shortlisting rises steeply
    once the skill match clears roughly 60% (the squared term).
    """
    s = sub_scores["skills"]
    return [
        s,
        sub_scores["qualification"],
        sub_scores["location"],
        sub_scores["stipend"],
        sub_scores["experience"],
        s * sub_scores["location"],
        s * s,
    ]


FEATURE_NAMES = [
    "skill_score", "qualification_score", "location_score", "stipend_score",
    "experience_score", "skill_x_location", "skill_squared",
]


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------
SORT_OPTIONS = {
    "match": ("Match score", "Ranked by the transparent weighted score."),
    "ml": ("AI shortlist likelihood", "Re-ranked by the ML model's shortlist probability."),
}


def sort_results(results, sort_by="match"):
    """
    Sort a list of {"match": {...}} entries in place and return it.
    Default keeps the displayed percentages in descending order; "ml" hands the
    ordering to the model. See the module docstring for why this is a choice.
    """
    if sort_by == "ml":
        results.sort(key=lambda r: (r["match"]["rank_score"], r["match"]["rule_score"]),
                     reverse=True)
    else:
        results.sort(key=lambda r: (r["match"]["rule_score"], r["match"]["ml_score"] or 0),
                     reverse=True)
    return results


# ---------------------------------------------------------------------------
# Bulk helpers used by the routes
# ---------------------------------------------------------------------------

def load_internships(conn, filters=None):
    """
    Active internships + company name, with optional SQL-side filtering.
    All values go through ? placeholders.
    """
    filters = filters or {}
    sql = """
        SELECT i.*, c.company_name, c.industry, c.website
        FROM internships i
        JOIN companies c ON c.id = i.company_id
        WHERE i.is_active = 1
    """
    params = []

    if filters.get("q"):
        sql += """ AND (i.title LIKE ? OR i.description LIKE ?
                        OR c.company_name LIKE ? OR i.domain LIKE ?)"""
        like = f"%{filters['q']}%"
        params += [like, like, like, like]
    if filters.get("location"):
        sql += " AND i.location = ?"
        params.append(filters["location"])
    if filters.get("domain"):
        sql += " AND i.domain = ?"
        params.append(filters["domain"])
    if filters.get("min_stipend"):
        sql += " AND MAX(i.stipend_min, i.stipend_max) >= ?"
        params.append(int(filters["min_stipend"]))
    if filters.get("duration"):
        sql += " AND i.duration_months <= ?"
        params.append(int(filters["duration"]))
    if filters.get("company_id"):
        sql += " AND i.company_id = ?"
        params.append(int(filters["company_id"]))
    if filters.get("skill"):
        sql += """ AND i.id IN (SELECT ins.internship_id FROM internship_skills ins
                                JOIN skills sk ON sk.id = ins.skill_id
                                WHERE sk.name = ? COLLATE NOCASE)"""
        params.append(filters["skill"])

    sql += " ORDER BY i.created_at DESC, i.id DESC"
    return query_all(conn, sql, tuple(params))


def recommend_for_student(conn, student, filters=None, limit=None, use_ml=True,
                          sort_by="match"):
    """
    Score every (filtered) internship for one student, best match first.
    Returns a list of dicts: {"internship": row, "match": score_match(...)}
    """
    student = _as_dict(student)
    internships = load_internships(conn, filters)
    if not internships:
        return []

    skills_by_internship = all_internship_skills(conn)
    student_skills = _student_skills(conn, student["id"])

    results = []
    for row in internships:
        skills = skills_by_internship.get(row["id"], {"required": [], "preferred": []})
        match = score_match(student, row, student_skills, skills, use_ml=use_ml)
        results.append({"internship": row, "match": match})

    sort_results(results, sort_by)
    return results[:limit] if limit else results


def _student_skills(conn, student_id):
    rows = query_all(
        conn,
        """SELECT s.name FROM student_skills ss JOIN skills s ON s.id = ss.skill_id
           WHERE ss.student_id = ?""",
        (student_id,),
    )
    return [r["name"] for r in rows]


def rank_candidates(conn, internship, limit=None, use_ml=True, sort_by="match"):
    """
    The company side of the same engine: score every student who has a profile
    against ONE internship, best candidate first.
    """
    internship = _as_dict(internship)
    students = query_all(
        conn,
        """SELECT sp.*, u.name, u.email FROM student_profiles sp
           JOIN users u ON u.id = sp.user_id""",
    )
    if not students:
        return []

    skills = internship_skill_map(conn, internship["id"])

    # All student skills in one query, grouped in Python.
    skill_rows = query_all(
        conn,
        """SELECT ss.student_id, s.name FROM student_skills ss
           JOIN skills s ON s.id = ss.skill_id""",
    )
    by_student = {}
    for row in skill_rows:
        by_student.setdefault(row["student_id"], []).append(row["name"])

    applied = {
        r["student_id"]: r["status"] for r in query_all(
            conn, "SELECT student_id, status FROM applications WHERE internship_id = ?",
            (internship["id"],),
        )
    }

    results = []
    for student in students:
        student_skills = by_student.get(student["id"], [])
        if not student_skills:
            continue  # nothing to match on yet
        match = score_match(student, internship, student_skills, skills, use_ml=use_ml)
        results.append({
            "student": student,
            "match": match,
            "application_status": applied.get(student["id"]),
        })

    sort_results(results, sort_by)
    return results[:limit] if limit else results


# ---------------------------------------------------------------------------
# Skill gap analysis (writes the skill_gaps table)
# ---------------------------------------------------------------------------

def refresh_skill_gaps(conn, student_id, recommendations, top_n=10):
    """
    Recompute this student's gaps from their top-N recommended internships and
    cache them in `skill_gaps`. Academia's dashboard reads the aggregate of this
    table, so the college view is driven by real matching output.
    """
    counts = {}
    for entry in recommendations[:top_n]:
        for skill in entry["match"]["missing_required"]:
            counts[skill] = counts.get(skill, 0) + 1
        for skill in entry["match"]["missing_preferred"]:
            counts[skill] = counts.get(skill, 0) + 1

    conn.execute("DELETE FROM skill_gaps WHERE student_id = ?", (student_id,))
    for name, count in counts.items():
        row = query_one(conn, "SELECT id FROM skills WHERE name = ? COLLATE NOCASE", (name,))
        if not row:
            continue
        conn.execute(
            """INSERT OR REPLACE INTO skill_gaps (student_id, skill_id, demand_count)
               VALUES (?, ?, ?)""",
            (student_id, row["id"], count),
        )
    conn.commit()
    return counts


def skill_gap_report(conn, student_id):
    """
    The student's Skill Gap page: missing skills ordered by how many recommended
    internships wanted them, each with suggested courses from the `courses` table.
    """
    rows = query_all(
        conn,
        """SELECT g.demand_count, s.id AS skill_id, s.name, s.category
           FROM skill_gaps g JOIN skills s ON s.id = g.skill_id
           WHERE g.student_id = ?
           ORDER BY g.demand_count DESC, s.name""",
        (student_id,),
    )
    report = []
    for row in rows:
        courses = query_all(
            conn,
            """SELECT title, provider, url, level, duration, is_free
               FROM courses WHERE skill_id = ? ORDER BY id""",
            (row["skill_id"],),
        )
        report.append({
            "skill": row["name"],
            "category": row["category"],
            "demand_count": row["demand_count"],
            "courses": courses,
        })
    return report


def save_application(conn, student_id, internship_id, match_score):
    """Insert an application, ignoring a duplicate apply."""
    cursor = conn.execute(
        """INSERT OR IGNORE INTO applications (internship_id, student_id, match_score)
           VALUES (?, ?, ?)""",
        (internship_id, student_id, match_score),
    )
    conn.commit()
    return cursor.rowcount > 0  # False => already applied
