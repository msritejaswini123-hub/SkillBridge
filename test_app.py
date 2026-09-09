"""
test_app.py
===========
Smoke tests for SkillBridge. They run against a throwaway copy of the database,
so your real database/portal.db is never touched.

Run:  python -m unittest test_app -v
  or: python test_app.py
"""

import io
import os
import shutil
import tempfile
import unittest

import database

# ---------------------------------------------------------------------------
# Point the database module at a temporary file BEFORE the app connects to it.
# ---------------------------------------------------------------------------
_TMP_DIR = tempfile.mkdtemp(prefix="skillbridge_test_")
database.DB_DIR = _TMP_DIR
database.DB_PATH = os.path.join(_TMP_DIR, "test_portal.db")

# Resume uploads made by the tests go here too (see SkillBridgeTest.setUpClass).
_UPLOAD_DIR = os.path.join(_TMP_DIR, "uploads")
os.makedirs(_UPLOAD_DIR, exist_ok=True)

import app as flask_app                      # noqa: E402  (after the patch above)
import analytics                             # noqa: E402
import recommendation                        # noqa: E402
import resume_parser as rp                   # noqa: E402
import seed_data                             # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_PDF = os.path.join(BASE_DIR, "sample_data", "sample_resume.pdf")
PASSWORD = seed_data.DEMO_PASSWORD


def setUpModule():
    database.init_db()
    conn = database.connect()
    try:
        seed_data.seed(conn, verbose=False)
    finally:
        conn.close()


def tearDownModule():
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


class SkillBridgeTest(unittest.TestCase):
    """Shared helpers."""

    @classmethod
    def setUpClass(cls):
        flask_app.app.config["TESTING"] = True
        flask_app.app.config["WTF_CSRF_ENABLED"] = False
        # Uploads during tests must land in the temp folder, not the real
        # uploads/ directory - otherwise running the tests litters the project.
        flask_app.app.config["UPLOAD_FOLDER"] = _UPLOAD_DIR

    def setUp(self):
        self.client = flask_app.app.test_client()

    def login(self, email, password=PASSWORD):
        return self.client.post("/login", data={"email": email, "password": password},
                                follow_redirects=True)

    def logout(self):
        return self.client.get("/logout", follow_redirects=True)


# ===========================================================================
# 1. RESUME PARSER
# ===========================================================================
class TestResumeParser(SkillBridgeTest):

    def test_extracts_the_demo_skills(self):
        text = "B.Tech CSE student with experience in Python, SQL, HTML, CSS and Flask."
        skills = rp.extract_skills(text)
        for expected in ["Python", "SQL", "HTML", "CSS", "Flask"]:
            self.assertIn(expected, skills)

    def test_extracts_qualification(self):
        degree, branch = rp.extract_qualification(
            "B.Tech CSE student with experience in Python.")
        self.assertEqual(degree, "B.Tech")
        self.assertEqual(branch, "CSE")

    def test_normalises_spellings(self):
        self.assertEqual(rp.normalize_skill("sklearn"), "Scikit-learn")
        self.assertEqual(rp.normalize_skill("HTML5"), "HTML")
        self.assertEqual(rp.normalize_skill("power-bi"), "Power BI")
        self.assertEqual(rp.normalize_skill("nodejs"), "Node.js")

    def test_no_false_positives_from_english_words(self):
        """The classic traps: 'go' the verb, 'it' the pronoun, a middle initial R."""
        text = "Rahul R Sharma will go to the lab. It is a good idea to be there."
        skills = rp.extract_skills(text)
        self.assertNotIn("Go", skills)
        self.assertNotIn("R", skills)
        degree, branch = rp.extract_qualification(text)
        self.assertIsNone(degree)
        self.assertIsNone(branch)

    def test_c_does_not_match_inside_cse(self):
        skills = rp.extract_skills("B.Tech CSE, knows CSS")
        self.assertNotIn("C", skills)
        self.assertIn("CSS", skills)

    def test_cpp_matches_itself(self):
        self.assertIn("C++", rp.extract_skills("Languages: C++, Java"))

    def test_experience_months(self):
        self.assertEqual(rp.extract_experience_months("3 months internship"), 3)
        self.assertEqual(rp.extract_experience_months("1 year experience"), 12)
        self.assertEqual(rp.extract_experience_months("no numbers here"), 0)

    def test_reads_the_sample_pdf(self):
        self.assertTrue(os.path.exists(SAMPLE_PDF),
                        "run: python tools/make_sample_resume.py")
        parsed = rp.parse_resume(SAMPLE_PDF)
        self.assertEqual(parsed["qualification"], "B.Tech CSE")
        self.assertIn("Python", parsed["skills"])
        self.assertIn("Flask", parsed["skills"])
        self.assertGreater(len(parsed["text"]), 100)

    def test_rejects_a_non_pdf(self):
        path = os.path.join(_TMP_DIR, "not_a_pdf.pdf")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("I am plain text pretending to be a PDF")
        with self.assertRaises(rp.ResumeError):
            rp.parse_resume(path)


# ===========================================================================
# 2. RECOMMENDATION ENGINE
# ===========================================================================
class TestRecommendationEngine(SkillBridgeTest):

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(recommendation.WEIGHTS.values()), 1.0, places=6)

    def test_skill_scoring_maths(self):
        # 2 of 3 required, 0 of 0 preferred -> 0.667
        score, detail = recommendation.score_skills(
            ["Python", "SQL"], ["Python", "SQL", "Flask"], [])
        self.assertAlmostEqual(score, 2 / 3, places=3)
        self.assertEqual(detail["missing_required"], ["Flask"])
        # a preferred skill is worth half
        score, _ = recommendation.score_skills(["Python"], ["Python"], ["Docker"])
        self.assertAlmostEqual(score, 1 / 1.5, places=3)

    def test_perfect_skill_match(self):
        score, detail = recommendation.score_skills(
            ["Python", "SQL", "Flask"], ["Python", "SQL", "Flask"], [])
        self.assertEqual(score, 1.0)
        self.assertEqual(detail["missing_required"], [])

    def test_location_rules(self):
        self.assertEqual(recommendation.score_location("Hyderabad", "Hyderabad")[0], 1.0)
        self.assertEqual(recommendation.score_location("Hyderabad", "Remote")[0], 1.0)
        self.assertEqual(recommendation.score_location("", "Chennai")[0], 1.0)
        near = recommendation.score_location("Mumbai", "Pune")[0]
        far = recommendation.score_location("Hyderabad", "Chennai")[0]
        self.assertGreater(near, far)

    def test_stipend_rules(self):
        # offer inside the expected range
        self.assertEqual(recommendation.score_stipend(10000, 20000, 15000, 15000)[0], 1.0)
        # offer above the range is still fine for the student
        self.assertEqual(recommendation.score_stipend(10000, 20000, 30000, 30000)[0], 1.0)
        # offer below the minimum gets proportional credit
        score, _ = recommendation.score_stipend(10000, 20000, 8000, 8000)
        self.assertAlmostEqual(score, 0.8, places=2)

    def test_qualification_rules(self):
        self.assertEqual(recommendation.score_qualification("B.Tech", "CSE", "Any Degree")[0], 1.0)
        self.assertEqual(recommendation.score_qualification("B.Tech", "CSE", "B.Tech CSE")[0], 1.0)
        exact = recommendation.score_qualification("B.Tech", "CSE", "B.Tech CSE / IT")[0]
        wrong_branch = recommendation.score_qualification("B.Tech", "ECE", "B.Tech CSE / IT")[0]
        self.assertEqual(exact, 1.0)
        self.assertLess(wrong_branch, exact)

    def test_qualification_detail_keeps_capitalisation(self):
        _, detail = recommendation.score_qualification("B.Tech", "CSE", "B.Tech CSE")
        self.assertIn("B.Tech", detail)     # not "b.tech"

    def test_breakdown_adds_up_to_the_displayed_score(self):
        conn = database.connect()
        try:
            student = database.query_one(
                conn,
                """SELECT sp.* FROM student_profiles sp JOIN users u ON u.id = sp.user_id
                   WHERE u.email = ?""", ("rahul@demo.com",))
            results = recommendation.recommend_for_student(conn, student, limit=5)
            self.assertTrue(results)
            for entry in results:
                match = entry["match"]
                total = sum(part["points"] for part in match["breakdown"])
                self.assertAlmostEqual(total, match["rule_score"], places=1)
                self.assertEqual(match["score"], round(match["rule_score"]))
        finally:
            conn.close()

    def test_default_order_matches_the_displayed_percentages(self):
        """
        The bug this guards against: sorting by the ML-blended key while showing
        the rule score renders a 74% above a 77% and looks broken. The default
        ordering must always read top-to-bottom in descending displayed score.
        """
        conn = database.connect()
        try:
            student = database.query_one(
                conn,
                """SELECT sp.* FROM student_profiles sp JOIN users u ON u.id = sp.user_id
                   WHERE u.email = ?""", ("rahul@demo.com",))
            results = recommendation.recommend_for_student(conn, student)
            shown = [entry["match"]["score"] for entry in results]
            self.assertEqual(shown, sorted(shown, reverse=True))
            for entry in results:
                self.assertGreaterEqual(entry["match"]["score"], 0)
                self.assertLessEqual(entry["match"]["score"], 100)
        finally:
            conn.close()

    def test_ml_sort_order_is_available_and_may_differ(self):
        conn = database.connect()
        try:
            student = database.query_one(
                conn,
                """SELECT sp.* FROM student_profiles sp JOIN users u ON u.id = sp.user_id
                   WHERE u.email = ?""", ("rahul@demo.com",))
            by_ml = recommendation.recommend_for_student(conn, student, sort_by="ml")
            keys = [entry["match"]["rank_score"] for entry in by_ml]
            self.assertEqual(keys, sorted(keys, reverse=True))
            # both orderings contain exactly the same internships
            by_match = recommendation.recommend_for_student(conn, student)
            self.assertEqual(
                sorted(e["internship"]["id"] for e in by_ml),
                sorted(e["internship"]["id"] for e in by_match))
        finally:
            conn.close()

    def test_candidate_default_order_matches_displayed_scores(self):
        conn = database.connect()
        try:
            job = database.query_one(
                conn, "SELECT * FROM internships WHERE title = ?", ("Python Developer Intern",))
            ranked = recommendation.rank_candidates(conn, job)
            shown = [row["match"]["score"] for row in ranked]
            self.assertEqual(shown, sorted(shown, reverse=True))
        finally:
            conn.close()

    def test_demo_student_matches_the_python_role_strongly(self):
        """Rahul has Python, SQL, Flask and Git - he should score highly."""
        conn = database.connect()
        try:
            student = database.query_one(
                conn,
                """SELECT sp.* FROM student_profiles sp JOIN users u ON u.id = sp.user_id
                   WHERE u.email = ?""", ("rahul@demo.com",))
            job = database.query_one(
                conn, "SELECT * FROM internships WHERE title = ?", ("Python Developer Intern",))
            match = recommendation.score_match(
                student, job, database.student_skill_names(conn, student["id"]),
                database.internship_skill_map(conn, job["id"]))
            self.assertGreaterEqual(match["score"], 85)
            self.assertEqual(match["missing_required"], [])
        finally:
            conn.close()

    def test_candidate_ranking_orders_students_sensibly(self):
        conn = database.connect()
        try:
            job = database.query_one(
                conn, "SELECT * FROM internships WHERE title = ?", ("Python Developer Intern",))
            ranked = recommendation.rank_candidates(conn, job)
            self.assertGreaterEqual(len(ranked), 3)
            names = [row["student"]["name"] for row in ranked]
            self.assertEqual(names[0], "Rahul Verma")
            scores = [row["match"]["score"] for row in ranked]
            self.assertEqual(scores, sorted(scores, reverse=True))
        finally:
            conn.close()

    def test_skill_gaps_are_written_to_the_table(self):
        conn = database.connect()
        try:
            student = database.query_one(
                conn,
                """SELECT sp.* FROM student_profiles sp JOIN users u ON u.id = sp.user_id
                   WHERE u.email = ?""", ("arjun@demo.com",))
            results = recommendation.recommend_for_student(conn, student)
            recommendation.refresh_skill_gaps(conn, student["id"], results)
            rows = database.query_all(
                conn, "SELECT * FROM skill_gaps WHERE student_id = ?", (student["id"],))
            self.assertTrue(rows)
            report = recommendation.skill_gap_report(conn, student["id"])
            self.assertTrue(report)
            self.assertIn("skill", report[0])
            self.assertIn("courses", report[0])
        finally:
            conn.close()


# ===========================================================================
# 3. ML LAYER
# ===========================================================================
class TestMLLayer(SkillBridgeTest):

    def test_model_reports_its_status_honestly(self):
        from ml.model import model_info
        info = model_info()
        self.assertIn("available", info)
        if info["available"]:
            self.assertIn("SYNTHETIC", info["data_note"].upper())
            self.assertEqual(len(info["coefficients"]), 7)
            self.assertGreater(info["roc_auc"], 0.6)
        else:
            self.assertIn("reason", info)

    def test_prediction_is_a_probability_or_none(self):
        from ml.model import predict_probability
        result = predict_probability([1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
        if result is not None:
            self.assertGreaterEqual(result, 0.0)
            self.assertLessEqual(result, 1.0)

    def test_bad_input_does_not_crash(self):
        from ml.model import predict_probability
        self.assertIsNone(predict_probability([]))
        self.assertIsNone(predict_probability([1.0, 2.0]))       # wrong length

    def test_ml_never_changes_the_displayed_score(self):
        sub = {"skills": .8, "qualification": 1.0, "location": 1.0,
               "stipend": 1.0, "experience": .5}
        features = recommendation.build_features(sub)
        self.assertEqual(len(features), 7)
        student = {"qualification": "B.Tech", "branch": "CSE",
                   "preferred_location": "Hyderabad", "min_stipend": 10000,
                   "max_stipend": 20000, "experience_months": 3, "projects_text": "Flask"}
        job = {"qualification": "B.Tech CSE", "location": "Hyderabad",
               "stipend_min": 15000, "stipend_max": 15000, "domain": "Web Development"}
        skills = {"required": ["Python", "Flask"], "preferred": []}
        with_ml = recommendation.score_match(student, job, ["Python", "Flask"], skills, use_ml=True)
        without = recommendation.score_match(student, job, ["Python", "Flask"], skills, use_ml=False)
        self.assertEqual(with_ml["score"], without["score"])
        self.assertEqual(with_ml["rule_score"], without["rule_score"])


# ===========================================================================
# 4. ANALYTICS
# ===========================================================================
class TestAnalytics(SkillBridgeTest):

    def test_counts_reflect_the_seed_data(self):
        conn = database.connect()
        try:
            stats = analytics.counts(conn)
            self.assertEqual(stats["internships"], len(seed_data.INTERNSHIPS))
            self.assertEqual(stats["companies"], len(seed_data.COMPANIES))
            self.assertEqual(stats["students"], len(seed_data.STUDENTS))
            self.assertGreater(stats["applications"], 0)
        finally:
            conn.close()

    def test_demand_vs_supply_percentages_are_sane(self):
        conn = database.connect()
        try:
            rows = analytics.demand_vs_supply(conn, 10)
            self.assertTrue(rows)
            for row in rows:
                self.assertGreaterEqual(row["demand_percent"], 0)
                self.assertLessEqual(row["demand_percent"], 100)
                self.assertLessEqual(row["supply_percent"], 100)
                self.assertAlmostEqual(
                    row["gap"], row["demand_percent"] - row["supply_percent"], places=1)
        finally:
            conn.close()

    def test_biggest_gaps_are_positive_and_sorted(self):
        conn = database.connect()
        try:
            gaps = analytics.biggest_gaps(conn, 8)
            values = [row["gap"] for row in gaps]
            self.assertEqual(values, sorted(values, reverse=True))
            for value in values:
                self.assertGreater(value, 0)
        finally:
            conn.close()

    def test_placement_stats_shape(self):
        conn = database.connect()
        try:
            stats = analytics.placement_stats(conn)
            self.assertEqual(len(stats["funnel"]), 5)
            self.assertTrue(stats["by_branch"])
            self.assertGreaterEqual(stats["avg_match_score"], 0)
        finally:
            conn.close()


# ===========================================================================
# 5. PUBLIC ROUTES
# ===========================================================================
class TestPublicRoutes(SkillBridgeTest):

    def test_public_pages_load(self):
        for path in ["/", "/login", "/register", "/internships", "/ml-info"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)

    def test_internship_detail_loads_for_a_visitor(self):
        response = self.client.get("/internship/1")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Role details", response.data)

    def test_missing_internship_gives_a_friendly_404(self):
        response = self.client.get("/internship/999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Page not found", response.data)

    def test_filters_actually_filter(self):
        all_results = self.client.get("/api/internships").get_json()
        hyderabad = self.client.get("/api/internships?location=Hyderabad").get_json()
        self.assertLess(len(hyderabad), len(all_results))
        self.assertTrue(all(row["location"] == "Hyderabad" for row in hyderabad))

        by_skill = self.client.get("/api/internships?skill=Flask").get_json()
        self.assertTrue(by_skill)
        for row in by_skill:
            self.assertIn("Flask", row["required_skills"] + row["preferred_skills"])

        rich = self.client.get("/api/internships?min_stipend=20000").get_json()
        for row in rich:
            self.assertGreaterEqual(max(row["stipend_min"], row["stipend_max"]), 20000)

    def test_search_filter(self):
        results = self.client.get("/api/internships?q=Python").get_json()
        self.assertTrue(results)

    def test_skills_api(self):
        names = self.client.get("/api/skills?q=pyth").get_json()
        self.assertIn("Python", names)

    def test_protected_pages_redirect_anonymous_users(self):
        for path in ["/student/dashboard", "/company/dashboard", "/academia/dashboard"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])


# ===========================================================================
# 6. AUTH
# ===========================================================================
class TestAuth(SkillBridgeTest):

    def test_login_and_logout(self):
        response = self.login("rahul@demo.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Logged in as", response.data)
        response = self.logout()
        self.assertIn(b"logged out", response.data)

    def test_wrong_password_is_rejected(self):
        response = self.client.post("/login",
                                    data={"email": "rahul@demo.com", "password": "wrong"})
        self.assertEqual(response.status_code, 401)
        self.assertIn(b"Incorrect email or password", response.data)

    def test_unknown_email_gives_the_same_message(self):
        """Never reveal whether an email exists."""
        response = self.client.post("/login",
                                    data={"email": "nobody@nowhere.com", "password": "x"})
        self.assertIn(b"Incorrect email or password", response.data)

    def test_password_is_hashed_in_the_database(self):
        conn = database.connect()
        try:
            row = database.query_one(
                conn, "SELECT password_hash FROM users WHERE email = ?", ("rahul@demo.com",))
            self.assertNotIn(PASSWORD, row["password_hash"])
            self.assertGreater(len(row["password_hash"]), 40)
        finally:
            conn.close()

    def test_registration_creates_a_working_student(self):
        response = self.client.post("/register", data={
            "role": "student", "name": "New Tester", "email": "new.tester@example.com",
            "password": "secret123", "confirm_password": "secret123",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome to SkillBridge", response.data)
        response = self.client.get("/student/dashboard")
        self.assertEqual(response.status_code, 200)

    def test_duplicate_email_is_rejected(self):
        response = self.client.post("/register", data={
            "role": "student", "name": "Copy Cat", "email": "rahul@demo.com",
            "password": "secret123", "confirm_password": "secret123",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"already exists", response.data)

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post("/register", data={
            "role": "student", "name": "Oops", "email": "oops@example.com",
            "password": "secret123", "confirm_password": "different",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"do not match", response.data)


# ===========================================================================
# 7. ROLE BASED AUTHORISATION
# ===========================================================================
class TestAuthorisation(SkillBridgeTest):

    def test_student_cannot_open_company_pages(self):
        self.login("rahul@demo.com")
        for path in ["/company/dashboard", "/company/post-internship", "/company/candidates"]:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertIn(b"not available for your account type", response.data)

    def test_company_cannot_open_student_pages(self):
        self.login("hr@technova.com")
        for path in ["/student/dashboard", "/student/recommendations", "/student/skill-gap"]:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertIn(b"not available for your account type", response.data)

    def test_academia_cannot_post_internships(self):
        self.login("dean@cvr.edu.in")
        response = self.client.get("/company/post-internship", follow_redirects=True)
        self.assertIn(b"not available for your account type", response.data)

    def test_company_cannot_touch_another_companys_internship(self):
        conn = database.connect()
        try:
            other = database.query_one(
                conn,
                """SELECT i.id FROM internships i JOIN companies c ON c.id = i.company_id
                   JOIN users u ON u.id = c.user_id WHERE u.email = ?""",
                ("hr@datasphere.com",))
        finally:
            conn.close()
        self.login("hr@technova.com")
        response = self.client.get(f"/company/candidates/{other['id']}")
        self.assertEqual(response.status_code, 403)


# ===========================================================================
# 8. THE FULL STUDENT DEMO FLOW
# ===========================================================================
class TestStudentFlow(SkillBridgeTest):

    def test_all_student_pages_load(self):
        self.login("rahul@demo.com")
        for path in ["/student/dashboard", "/student/profile", "/student/resume",
                     "/student/skills", "/student/recommendations", "/student/skill-gap",
                     "/student/applications", "/student/saved", "/internships"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)

    def test_recommendations_show_a_match_percentage(self):
        self.login("rahul@demo.com")
        response = self.client.get("/student/recommendations")
        self.assertIn(b"ranked by match score", response.data)
        self.assertIn(b"match-pill", response.data)      # the score badge rendered
        self.assertIn(b"best match", response.data)
        self.assertIn(b"Required skills", response.data)

    def test_sort_toggle_renders_and_works(self):
        self.login("rahul@demo.com")
        response = self.client.get("/student/recommendations")
        self.assertIn(b"Sort by", response.data)
        self.assertIn(b"AI shortlist likelihood", response.data)
        response = self.client.get("/student/recommendations?sort=ml")
        self.assertEqual(response.status_code, 200)
        # an unknown sort value falls back to the default instead of erroring
        response = self.client.get("/student/recommendations?sort=nonsense")
        self.assertEqual(response.status_code, 200)

    def test_internship_detail_shows_matched_and_missing_skills(self):
        self.login("rahul@demo.com")
        conn = database.connect()
        try:
            job = database.query_one(
                conn, "SELECT id FROM internships WHERE title = ?", ("Data Analyst Intern",))
        finally:
            conn.close()
        response = self.client.get(f"/internship/{job['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Matched skills", response.data)
        self.assertIn(b"Missing skills", response.data)
        self.assertIn(b"Score breakdown", response.data)

    def test_the_whole_registration_to_application_journey(self):
        """The exact demo flow: register, upload resume, save skills, set
        preferences, get recommendations, apply, see the application."""
        # 1. register
        self.client.post("/register", data={
            "role": "student", "name": "Journey Student",
            "email": "journey@example.com", "password": "secret123",
            "confirm_password": "secret123",
        }, follow_redirects=True)

        # 2. upload the sample resume
        with open(SAMPLE_PDF, "rb") as handle:
            pdf_bytes = handle.read()
        response = self.client.post(
            "/student/resume",
            data={"resume": (io.BytesIO(pdf_bytes), "my_resume.pdf")},
            content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"skills found", response.data)
        self.assertIn(b"Review your extracted skills", response.data)

        # 3. confirm the extracted skills
        response = self.client.post("/student/skills", data={
            "skill": ["Python", "SQL", "HTML", "CSS", "Flask", "Git"],
            "extra_skills": "sklearn",        # tests normalisation on save
            "apply_qualification": "1", "degree": "B.Tech", "branch": "CSE",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Saved 7 skills", response.data)

        # 4. set location and stipend preferences
        response = self.client.post("/student/profile", data={
            "qualification": "B.Tech", "branch": "CSE", "college": "Test College",
            "graduation_year": "2026", "preferred_location": "Hyderabad",
            "min_stipend": "10000", "max_stipend": "20000", "phone": "9999999999",
            "experience_months": "3", "projects_text": "Portal using Flask and SQLite",
        }, follow_redirects=True)
        self.assertIn(b"Profile saved", response.data)

        # 5. recommendations exist and are ranked
        response = self.client.get("/student/recommendations")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"best match", response.data)

        # the engine agrees, with a strong top match
        conn = database.connect()
        try:
            profile = database.query_one(
                conn,
                """SELECT sp.* FROM student_profiles sp JOIN users u ON u.id = sp.user_id
                   WHERE u.email = ?""", ("journey@example.com",))
            self.assertEqual(profile["qualification"], "B.Tech")
            self.assertEqual(profile["preferred_location"], "Hyderabad")
            skills = database.student_skill_names(conn, profile["id"])
            self.assertIn("Scikit-learn", skills)     # 'sklearn' was normalised
            results = recommendation.recommend_for_student(conn, profile, limit=3)
            self.assertTrue(results)
            self.assertGreaterEqual(results[0]["match"]["score"], 70)
            target_id = results[0]["internship"]["id"]
        finally:
            conn.close()

        # 6. skill gap page works
        response = self.client.get("/student/skill-gap")
        self.assertEqual(response.status_code, 200)

        # 7. apply
        response = self.client.post(f"/internship/{target_id}/apply", follow_redirects=True)
        self.assertIn(b"Applied to", response.data)

        # 8. applying twice is handled
        response = self.client.post(f"/internship/{target_id}/apply", follow_redirects=True)
        self.assertIn(b"already applied", response.data)

        # 9. it shows on the applications page and in the database
        response = self.client.get("/student/applications")
        self.assertEqual(response.status_code, 200)
        conn = database.connect()
        try:
            row = database.query_one(
                conn,
                """SELECT a.* FROM applications a JOIN student_profiles sp ON sp.id = a.student_id
                   JOIN users u ON u.id = sp.user_id
                   WHERE u.email = ? AND a.internship_id = ?""",
                ("journey@example.com", target_id))
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "Applied")
            self.assertGreater(row["match_score"], 0)
        finally:
            conn.close()

    def test_save_and_unsave_an_internship(self):
        self.login("priya@demo.com")
        response = self.client.post("/internship/2/save", follow_redirects=True)
        self.assertIn(b"Saved for later", response.data)
        response = self.client.post("/internship/2/save", follow_redirects=True)
        self.assertIn(b"Removed from your saved list", response.data)

    def test_upload_rejects_a_fake_pdf(self):
        self.login("rahul@demo.com")
        response = self.client.post(
            "/student/resume",
            data={"resume": (io.BytesIO(b"just text, not a pdf"), "fake.pdf")},
            content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"not a real PDF", response.data)

    def test_upload_rejects_a_non_pdf_extension(self):
        self.login("rahul@demo.com")
        response = self.client.post(
            "/student/resume",
            data={"resume": (io.BytesIO(b"%PDF-1.4 fake"), "resume.docx")},
            content_type="multipart/form-data", follow_redirects=True)
        self.assertIn(b"Only PDF resumes are accepted", response.data)

    def test_upload_with_no_file_is_handled(self):
        self.login("rahul@demo.com")
        response = self.client.post("/student/resume", data={},
                                    content_type="multipart/form-data",
                                    follow_redirects=True)
        self.assertIn(b"choose a PDF file", response.data)

    def test_saving_zero_skills_is_refused(self):
        self.login("priya@demo.com")
        response = self.client.post("/student/skills",
                                    data={"extra_skills": ""}, follow_redirects=True)
        self.assertIn(b"at least one skill", response.data)

    def test_swapped_stipend_range_is_corrected(self):
        self.login("arjun@demo.com")
        response = self.client.post("/student/profile", data={
            "qualification": "B.Tech", "branch": "ECE", "preferred_location": "Hyderabad",
            "min_stipend": "20000", "max_stipend": "8000",
        }, follow_redirects=True)
        self.assertIn(b"wrong way round", response.data)
        conn = database.connect()
        try:
            row = database.query_one(
                conn,
                """SELECT sp.min_stipend, sp.max_stipend FROM student_profiles sp
                   JOIN users u ON u.id = sp.user_id WHERE u.email = ?""",
                ("arjun@demo.com",))
            self.assertEqual(row["min_stipend"], 8000)
            self.assertEqual(row["max_stipend"], 20000)
        finally:
            conn.close()


# ===========================================================================
# 9. THE FULL COMPANY DEMO FLOW
# ===========================================================================
class TestCompanyFlow(SkillBridgeTest):

    def test_all_company_pages_load(self):
        self.login("hr@technova.com")
        for path in ["/company/dashboard", "/company/profile", "/company/post-internship",
                     "/company/internships", "/company/candidates",
                     "/company/candidates?sort=ml", "/company/applications"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)

    def test_posting_an_internship_and_getting_ranked_students(self):
        self.login("hr@technova.com")
        response = self.client.post("/company/post-internship", data={
            "title": "Test Flask Intern", "description": "Build internal tools.",
            "domain": "Web Development", "location": "Hyderabad",
            "stipend_min": "14000", "stipend_max": "18000", "duration_months": "6",
            "qualification": "B.Tech CSE / IT", "openings": "2",
            "required_skills": "Python, Flask, SQL",
            "preferred_skills": "Git, sklearn",
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"is live", response.data)
        self.assertIn(b"Recommended candidates", response.data)
        # a real student appears with a real percentage
        self.assertIn(b"Rahul Verma", response.data)

        conn = database.connect()
        try:
            job = database.query_one(
                conn, "SELECT * FROM internships WHERE title = ?", ("Test Flask Intern",))
            self.assertIsNotNone(job)
            self.assertEqual(job["is_demo"], 0)      # company-created, not demo
            skills = database.internship_skill_map(conn, job["id"])
            self.assertIn("Python", skills["required"])
            # 'sklearn' was normalised on the way in
            self.assertIn("Scikit-learn", skills["preferred"])
            ranked = recommendation.rank_candidates(conn, job)
            self.assertTrue(ranked)
            self.assertGreater(ranked[0]["match"]["score"], ranked[-1]["match"]["score"])
        finally:
            conn.close()

    def test_posting_without_required_skills_is_rejected(self):
        self.login("hr@technova.com")
        response = self.client.post("/company/post-internship", data={
            "title": "Bad Posting", "location": "Hyderabad", "required_skills": "",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"at least one required skill", response.data)

    def test_posting_without_a_title_is_rejected(self):
        self.login("hr@technova.com")
        response = self.client.post("/company/post-internship", data={
            "title": "", "location": "Pune", "required_skills": "Python",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"internship title", response.data)

    def test_company_can_update_an_application_status(self):
        self.login("hr@technova.com")
        conn = database.connect()
        try:
            row = database.query_one(
                conn,
                """SELECT a.id FROM applications a JOIN internships i ON i.id = a.internship_id
                   JOIN companies c ON c.id = i.company_id JOIN users u ON u.id = c.user_id
                   WHERE u.email = ? LIMIT 1""", ("hr@technova.com",))
        finally:
            conn.close()
        self.assertIsNotNone(row)
        response = self.client.post(f"/company/application/{row['id']}/status",
                                    data={"status": "Shortlisted"}, follow_redirects=True)
        self.assertIn(b"marked as Shortlisted", response.data)

    def test_invalid_status_is_rejected(self):
        self.login("hr@technova.com")
        conn = database.connect()
        try:
            row = database.query_one(
                conn,
                """SELECT a.id FROM applications a JOIN internships i ON i.id = a.internship_id
                   JOIN companies c ON c.id = i.company_id JOIN users u ON u.id = c.user_id
                   WHERE u.email = ? LIMIT 1""", ("hr@technova.com",))
        finally:
            conn.close()
        response = self.client.post(f"/company/application/{row['id']}/status",
                                    data={"status": "Hired Immediately"},
                                    follow_redirects=True)
        self.assertIn(b"Unknown application status", response.data)

    def test_closing_and_reopening_an_internship(self):
        self.login("hr@technova.com")
        conn = database.connect()
        try:
            job = database.query_one(
                conn,
                """SELECT i.id FROM internships i JOIN companies c ON c.id = i.company_id
                   JOIN users u ON u.id = c.user_id WHERE u.email = ? LIMIT 1""",
                ("hr@technova.com",))
        finally:
            conn.close()
        response = self.client.post(f"/company/internship/{job['id']}/toggle",
                                    follow_redirects=True)
        self.assertIn(b"closed", response.data)
        response = self.client.post(f"/company/internship/{job['id']}/toggle",
                                    follow_redirects=True)
        self.assertIn(b"reopened", response.data)


# ===========================================================================
# 10. THE ACADEMIA VIEW
# ===========================================================================
class TestAcademiaFlow(SkillBridgeTest):

    def test_academia_pages_load(self):
        self.login("dean@cvr.edu.in")
        for path in ["/academia/dashboard", "/academia/skill-demand"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, path)

    def test_dashboard_shows_demand_and_gaps(self):
        self.login("dean@cvr.edu.in")
        response = self.client.get("/academia/dashboard")
        self.assertIn(b"Industry skill demand vs student availability", response.data)
        self.assertIn(b"Where to focus the curriculum", response.data)
        self.assertIn(b"Placement funnel", response.data)
        self.assertIn(b"Branch-wise participation", response.data)

    def test_skill_demand_report_has_a_table_view(self):
        self.login("dean@cvr.edu.in")
        response = self.client.get("/academia/skill-demand")
        self.assertIn(b"Table view", response.data)
        self.assertIn(b"Student skill availability", response.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
