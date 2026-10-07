import os
import unittest
import sqlite3
import re
from app import app, init_db, get_db

class LifelongLearningEngagementTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True

    def setUp(self):
        self.client = app.test_client()

    def get_csrf_token(self, html):
        """Helper to extract CSRF token from rendered HTML."""
        match = re.search(r'name=["\']_csrf_token["\']\s+value=["\']([^"\']+)["\']', html)
        if match:
            return match.group(1)
        match = re.search(r'value=["\']([^"\']+)["\']\s+name=["\']_csrf_token["\']', html)
        if match:
            return match.group(1)
        return ""

    def test_01_public_pages_accessible(self):
        """Verify public pages render with HTTP 200."""
        for path in ["/", "/login", "/register"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, f"Failed to load {path}")
                self.assertIn(b"html", response.data.lower())

    def test_02_csrf_protection_rejects_missing_token_on_protected_endpoints(self):
        """Verify mutating POST requests without CSRF token are blocked with 403 Forbidden."""
        # 1. Login as admin first
        self.client.post("/login", data={
            "email": "admin@adaptivelearn.local",
            "password": "ChangeMe@123!"
        })

        # 2. Attempt POST to /admin/course/new without CSRF token
        response = self.client.post("/admin/course/new", data={
            "title": "CSRF Attack Course",
            "description": "This should be blocked",
            "level": "Beginner"
        })
        self.assertEqual(response.status_code, 403, "POST without CSRF token must return 403 Forbidden")

        self.client.get("/logout")

    def test_03_admin_login_and_dashboard_access(self):
        """Verify admin can log in and access admin areas."""
        # Step 1: POST login with valid credentials
        login_post = self.client.post("/login", data={
            "email": "admin@adaptivelearn.local",
            "password": "ChangeMe@123!"
        }, follow_redirects=True)
        self.assertEqual(login_post.status_code, 200)

        # Step 2: Access admin dashboard
        admin_resp = self.client.get("/admin")
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b"Admin", admin_resp.data)

        # Step 3: Access admin students list
        students_resp = self.client.get("/admin/students")
        self.assertEqual(students_resp.status_code, 200)

        # Step 4: Logout
        logout_resp = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(logout_resp.status_code, 200)

    def test_04_student_registration_and_catalog_flow(self):
        """Verify student registration, login, and access to student features."""
        # Step 1: Register new student
        unique_id = os.urandom(4).hex()
        student_email = f"student_{unique_id}@example.com"
        reg_post = self.client.post("/register", data={
            "name": f"Tester {unique_id}",
            "email": student_email,
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "career_goal": "Full Stack Engineer"
        }, follow_redirects=True)
        self.assertEqual(reg_post.status_code, 200)

        # Step 2: Login as the new student
        login_post = self.client.post("/login", data={
            "email": student_email,
            "password": "StrongPassword123!"
        }, follow_redirects=True)
        self.assertEqual(login_post.status_code, 200)

        # Step 3: Access student dashboard
        dash_resp = self.client.get("/student/dashboard")
        self.assertEqual(dash_resp.status_code, 200)

        # Step 4: Access course catalog
        courses_resp = self.client.get("/courses")
        self.assertEqual(courses_resp.status_code, 200)

        # Step 5: Role isolation - student cannot access /admin
        admin_resp = self.client.get("/admin", follow_redirects=False)
        self.assertIn(admin_resp.status_code, [302, 403])

        # Step 6: Logout
        self.client.get("/logout")

    def test_05_unauthorized_access_redirects_to_login(self):
        """Protected routes should redirect anonymous visitors to login."""
        protected_routes = ["/student/dashboard", "/student/learning-path", "/courses", "/admin", "/contact-admin"]
        for route in protected_routes:
            with self.subTest(route=route):
                resp = self.client.get(route)
                self.assertEqual(resp.status_code, 302)
                self.assertIn("/login", resp.headers.get("Location", ""))

    def test_06_database_schema_integrity(self):
        """Verify expected SQLite tables exist in database."""
        with app.app_context():
            db = get_db()
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            expected = {
                "users", "courses", "checkpoints", "assessments",
                "assessment_questions", "enrollments", "quiz_results",
                "notifications", "messages"
            }
            for t in expected:
                self.assertIn(t, tables, f"Expected table '{t}' missing from database")

    def test_07_course_creation_with_valid_csrf(self):
        """Verify admin can create a new course when providing a valid CSRF token."""
        # 1. Login as admin
        self.client.post("/login", data={
            "email": "admin@adaptivelearn.local",
            "password": "ChangeMe@123!"
        })

        # 2. GET course creation form to fetch CSRF token
        form_get = self.client.get("/admin/course/new")
        self.assertEqual(form_get.status_code, 200)
        token = self.get_csrf_token(form_get.data.decode("utf-8"))
        self.assertTrue(len(token) > 0, "CSRF token must be present in course creation form")

        # 3. POST new course
        course_title = f"Test Python Course {os.urandom(3).hex()}"
        post_resp = self.client.post("/admin/course/new", data={
            "_csrf_token": token,
            "title": course_title,
            "description": "Comprehensive course on Python programming.",
            "category": "Programming",
            "level": "Beginner",
            "career_target": "Software Engineer",
            "video_url": "https://www.youtube.com/watch?v=sample",
            "published": "1"
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)

        # 4. Verify course exists in DB
        with app.app_context():
            course = get_db().execute("SELECT * FROM courses WHERE title=?", (course_title,)).fetchone()
            self.assertIsNotNone(course)
            self.assertEqual(course["category"], "Programming")

        self.client.get("/logout")

if __name__ == "__main__":
    unittest.main()
