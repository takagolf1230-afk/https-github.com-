"""SNS向けアンケートの回答サーバー(Flask)。 起動: python app.py  / 本番: waitress-serve --port=8000 app:app

環境変数:
  ADMIN_PASSWORD  管理画面のパスワード(未設定なら管理画面は無効)
  SURVEY_DB       DBファイルのパス(既定: このフォルダの survey.db)
  TRUST_PROXY     1 のとき CF-Connecting-IP / X-Forwarded-For を回数制限に使う(トンネル/リバースプロキシ越し)
"""
from __future__ import annotations

import csv
import hashlib
import io
import os
import re
import secrets
import time
from collections import Counter, defaultdict

from werkzeug.datastructures import MultiDict
from flask import Flask, Response, abort, redirect, render_template, request, url_for

import storage
from questions import EMAIL_HELP, QUESTIONS

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
storage.init_db()

RATE_LIMIT = 20          # 同一端末からの送信上限(回/時間)
_hits: dict[str, list[float]] = defaultdict(list)
_salt = secrets.token_hex(8)  # 起動ごとに変わる。IPそのものは保存せず、回数制限にだけ使う
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def client_key() -> str:
    ip = request.remote_addr or ""
    if os.environ.get("TRUST_PROXY") == "1":
        ip = request.headers.get("CF-Connecting-IP") or (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()) or ip
    return hashlib.sha256((_salt + ip).encode()).hexdigest()


def rate_limited() -> bool:
    k, t = client_key(), time.time()
    _hits[k] = [x for x in _hits[k] if t - x < 3600]
    if len(_hits[k]) >= RATE_LIMIT:
        return True
    _hits[k].append(t)
    return False


def clean_source(s: str) -> str:
    s = (s or "").lower()
    return s if re.fullmatch(r"[a-z0-9_-]{1,20}", s) else ""


def validate(form) -> tuple[dict, list[str]]:
    answers, errors = {}, []
    for q in QUESTIONS:
        if q["type"] == "checkbox":
            vals = [v for v in form.getlist(q["id"]) if v in q["options"]]
            vals = list(dict.fromkeys(vals))
            if q.get("required") and not vals:
                errors.append(q["id"])
            if len(vals) > q.get("max_select", 99):
                errors.append(q["id"])
            answers[q["title"]] = ", ".join(vals)
        elif q["type"] == "radio":
            v = form.get(q["id"], "")
            if v and v not in q["options"]:
                v = ""
            if q.get("required") and not v:
                errors.append(q["id"])
            answers[q["title"]] = v
        else:
            v = (form.get(q["id"], "") or "").strip()[: q.get("max_length", 500)]
            if q.get("required") and not v:
                errors.append(q["id"])
            answers[q["title"]] = v
    return answers, errors


@app.get("/")
def index():
    return render_template("form.html", questions=QUESTIONS, errors=[], values=MultiDict(), email_help=EMAIL_HELP,
                           src=clean_source(request.args.get("src", "")))


@app.post("/submit")
def submit():
    if request.form.get("website"):            # ハニーポット(人間には見えない欄)
        return redirect(url_for("thanks"))
    if rate_limited():
        abort(429)
    answers, errors = validate(request.form)
    src = clean_source(request.form.get("src", ""))
    if errors:
        return render_template("form.html", questions=QUESTIONS, errors=errors, values=request.form,
                               email_help=EMAIL_HELP, src=src), 400
    email = (request.form.get("email", "") or "").strip()[:200]
    if email and not EMAIL_RE.match(email):
        email = ""
    storage.save_response(answers, src, email)
    return redirect(url_for("thanks"))


@app.get("/thanks")
def thanks():
    return render_template("thanks.html")


@app.get("/healthz")
def healthz():
    return "ok"


# ------------------------------------------------------------------ 管理画面
def require_admin():
    pw = os.environ.get("ADMIN_PASSWORD", "")
    if not pw:
        abort(404)  # パスワード未設定なら管理画面は存在しないことにする
    auth = request.authorization
    if not auth or not secrets.compare_digest(auth.password or "", pw):
        abort(Response("認証が必要です", 401, {"WWW-Authenticate": 'Basic realm="admin"'}))


def csv_safe(v: str) -> str:
    """Excel で開いたとき数式として実行されないようにする(CSVインジェクション対策)。"""
    v = str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


def to_csv(rows: list[dict], columns: list[str]) -> Response:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(columns)
    for r in rows:
        w.writerow([csv_safe(r.get(c, "")) for c in columns])
    data = "﻿" + buf.getvalue()  # BOM付きUTF-8(Excelで文字化けしない)
    return Response(data, mimetype="text/csv; charset=utf-8")


@app.get("/admin")
def admin():
    require_admin()
    rows = storage.all_responses()
    by_day = Counter(r["created_at"][:10] for r in rows)
    by_source = Counter(r["source"] or "(なし)" for r in rows)
    chore_title = next(q["title"] for q in QUESTIONS if q["id"] == "chores")
    chores = Counter(c for r in rows for c in r.get(chore_title, "").split(", ") if c)
    role_title = next(q["title"] for q in QUESTIONS if q["id"] == "role")
    roles = Counter(r.get(role_title, "") for r in rows)
    return render_template("admin.html", total=len(rows), by_day=sorted(by_day.items(), reverse=True)[:14],
                           by_source=by_source.most_common(), chores=chores.most_common(), roles=roles.most_common(),
                           leads=len(storage.all_leads()), recent=rows[-10:][::-1], questions=QUESTIONS)


@app.get("/admin/responses.csv")
def export_responses():
    require_admin()
    cols = ["回答日時", "流入元"] + [q["title"] for q in QUESTIONS]
    rows = [{"回答日時": r["created_at"], "流入元": r["source"], **r} for r in storage.all_responses()]
    resp = to_csv(rows, cols)
    resp.headers["Content-Disposition"] = "attachment; filename=responses.csv"
    return resp


@app.get("/admin/leads.csv")
def export_leads():
    require_admin()
    rows = [{"登録日時": r["created_at"], "メールアドレス": r["email"]} for r in storage.all_leads()]
    resp = to_csv(rows, ["登録日時", "メールアドレス"])
    resp.headers["Content-Disposition"] = "attachment; filename=leads.csv"
    return resp


@app.post("/admin/delete/<int:rid>")
def delete(rid: int):
    require_admin()
    storage.delete_response(rid)
    return redirect(url_for("admin"))


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/admin"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8000)), debug=False)
