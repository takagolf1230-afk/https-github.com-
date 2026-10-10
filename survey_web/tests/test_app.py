"""python -m unittest discover -s tests   (survey_web フォルダで実行)"""
import base64
import io
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SURVEY_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ["ADMIN_PASSWORD"] = "pw-test"

import app as survey  # noqa: E402
import storage  # noqa: E402

AUTH = {"Authorization": "Basic " + base64.b64encode(b"admin:pw-test").decode()}
GOOD = {"role": "診療放射線技師", "position": "中堅", "chores": ["勤務表・シフト作成", "記録・書類作成"],
        "pain": "勤務表に3時間かかる", "wish": "勤務表の自動作成", "src": "x"}


class T(unittest.TestCase):
    def setUp(self):
        survey.app.config["TESTING"] = True
        survey._hits.clear()
        self.c = survey.app.test_client()
        with storage.connect() as con:
            con.execute("DELETE FROM responses")
            con.execute("DELETE FROM leads")

    def test_form_renders(self):
        r = self.c.get("/?src=ig")
        self.assertEqual(r.status_code, 200)
        self.assertIn("name=\"src\" value=\"ig\"", r.get_data(as_text=True))

    def test_submit_ok(self):
        r = self.c.post("/submit", data={**GOOD, "email": "a@example.com"})
        self.assertEqual(r.status_code, 302)
        rows = storage.all_responses()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "x")
        self.assertEqual(rows[0]["負担が大きい雑務を、3つまで選んでください"], "勤務表・シフト作成, 記録・書類作成")
        self.assertEqual(storage.all_leads()[0]["email"], "a@example.com")

    def test_required_and_max_select(self):
        self.assertEqual(self.c.post("/submit", data={**GOOD, "role": ""}).status_code, 400)
        four = ["勤務表・シフト作成", "申し送り・引き継ぎ", "記録・書類作成", "物品・在庫管理"]
        self.assertEqual(self.c.post("/submit", data={**GOOD, "chores": four}).status_code, 400)
        self.assertEqual(len(storage.all_responses()), 0)

    def test_invalid_option_rejected(self):
        self.assertEqual(self.c.post("/submit", data={**GOOD, "position": "不明な立場"}).status_code, 400)

    def test_optional_questions_can_be_empty(self):
        d = {k: v for k, v in GOOD.items() if k not in ("pain", "wish")}
        self.assertEqual(self.c.post("/submit", data=d).status_code, 302)

    def test_region_optional_and_validated(self):
        self.assertEqual(self.c.post("/submit", data={**GOOD, "region": "九州・沖縄"}).status_code, 302)
        self.assertEqual(storage.all_responses()[0]["お住まいの地域"], "九州・沖縄")
        survey._hits.clear()
        self.assertEqual(self.c.post("/submit", data={**GOOD, "region": "火星"}).status_code, 302)  # 任意項目の不正値は保存しない
        self.assertEqual(storage.all_responses()[-1]["お住まいの地域"], "")

    def test_broad_medical_roles(self):
        roles = next(q for q in survey.QUESTIONS if q["id"] == "role")["options"]
        for r in ("医師", "歯科医師", "助産師・保健師", "介護職", "管理栄養士・栄養士"):
            self.assertIn(r, roles)

    def test_ogp_and_share(self):
        html = self.c.get("/").get_data(as_text=True)
        self.assertIn('property="og:title"', html)
        os.environ["BASE_URL"] = "https://example.com/"
        try:
            self.assertIn("https%3A//example.com/%3Fsrc%3Dshare", self.c.get("/thanks").get_data(as_text=True).replace("%3A%2F%2F", "%3A//"))
        finally:
            os.environ.pop("BASE_URL")

    def test_no_price_or_payer_question(self):
        titles = " ".join(q["title"] for q in survey.QUESTIONS)
        self.assertNotIn("いくらまで", titles)
        self.assertNotIn("負担しますか", titles)

    def test_honeypot_not_saved(self):
        self.c.post("/submit", data={**GOOD, "website": "http://spam"})
        self.assertEqual(len(storage.all_responses()), 0)

    def test_rate_limit(self):
        codes = [self.c.post("/submit", data=GOOD).status_code for _ in range(survey.RATE_LIMIT + 2)]
        self.assertEqual(codes[-1], 429)

    def test_bad_email_ignored_and_source_sanitized(self):
        self.c.post("/submit", data={**GOOD, "email": "not-an-email", "src": "<script>"})
        self.assertEqual(storage.all_leads(), [])
        self.assertEqual(storage.all_responses()[0]["source"], "")

    def test_admin_requires_auth(self):
        self.assertEqual(self.c.get("/admin").status_code, 401)
        self.assertEqual(self.c.get("/admin/responses.csv").status_code, 401)
        self.assertEqual(self.c.get("/admin/leads.csv").status_code, 401)
        self.assertEqual(self.c.post("/admin/delete/1").status_code, 401)
        self.assertEqual(self.c.get("/admin", headers=AUTH).status_code, 200)

    def test_admin_disabled_without_password(self):
        os.environ.pop("ADMIN_PASSWORD")
        try:
            self.assertEqual(self.c.get("/admin", headers=AUTH).status_code, 404)
        finally:
            os.environ["ADMIN_PASSWORD"] = "pw-test"

    def test_csv_injection_and_bom(self):
        self.c.post("/submit", data={**GOOD, "pain": "=HYPERLINK(\"http://x\")"})
        r = self.c.get("/admin/responses.csv", headers=AUTH)
        text = r.get_data(as_text=True)
        self.assertTrue(text.startswith("﻿"))
        self.assertIn("'=HYPERLINK", text)

    def test_csv_readable_by_analysis_app(self):
        for _ in range(3):
            self.c.post("/submit", data=GOOD)
            survey._hits.clear()
        text = self.c.get("/admin/responses.csv", headers=AUTH).get_data(as_text=True)
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "survey_needs"))
        import pandas as pd
        import analysis
        df = pd.read_csv(io.StringIO(text.lstrip("﻿")))
        cols = analysis.detect_columns(df)
        for key in ("role", "position", "chore_pick", "free_pain", "free_wish"):
            self.assertIsNotNone(cols[key], key)
        picks = analysis.multi_choice_counts(df, cols["chore_pick"])
        self.assertEqual(picks["勤務表・シフト作成"], 3)

    def test_delete(self):
        self.c.post("/submit", data=GOOD)
        rid = storage.all_responses()[0]["id"]
        self.c.post(f"/admin/delete/{rid}", headers=AUTH)
        self.assertEqual(storage.all_responses(), [])


if __name__ == "__main__":
    unittest.main()
