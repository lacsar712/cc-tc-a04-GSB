import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, OperationalError

from claimer import start as start_claimer
from models import (
    Base,
    ConvergenceLog,
    Pairing,
    SessionLocal,
    engine,
    pairing_dict,
    row_dict,
)
from rules import dual_diff, dual_reject_reason, judge_pair

SECRET = os.environ.get("JWT_SECRET", "tunnelconv-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "surveyor": {"role": "writer", "password_hash": pwd.hash("surv123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

app = Flask(__name__)


def ensure_schema():
    """旧库结构不含双路字段时重建（开发阶段种子可丢弃）。"""
    insp = inspect(engine)
    if "convergence_logs" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("convergence_logs")}
        if "section" not in cols:
            ConvergenceLog.__table__.drop(engine)
    Base.metadata.create_all(engine)


def seed():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        pairings = {}
        if db.query(Pairing).count() == 0:
            for section, lg, rg, th in (
                ("K12+180", "CJ-L-12180", "CJ-R-12180", 0.5),
                ("K18+040", "CJ-L-18040", "CJ-R-18040", 0.5),
            ):
                p = Pairing(
                    section=section,
                    left_gauge=lg,
                    right_gauge=rg,
                    threshold_mm=th,
                    created_by="surveyor",
                    created_at=now,
                    updated_at=now,
                )
                db.add(p)
                pairings[section] = p
            db.flush()
        if db.query(ConvergenceLog).count() == 0:

            def add_log(section, left, right, status):
                p = pairings.get(section) or db.query(Pairing).filter_by(section=section).first()
                row = ConvergenceLog(
                    section=section,
                    left_mm=left,
                    right_mm=right,
                    diff_mm=dual_diff(left, right),
                    status=status,
                    created_by="surveyor",
                    created_at=now,
                    processed_at=now,
                    pairing_id=p.id if p else None,
                    pair_left_gauge=p.left_gauge if p else None,
                    pair_right_gauge=p.right_gauge if p else None,
                    pair_threshold_mm=p.threshold_mm if p else None,
                )
                if status == "done":
                    row.verdict, row.reason = judge_pair(left, right)
                else:
                    row.reason = dual_reject_reason(left, right, p.threshold_mm)
                db.add(row)

            add_log("K12+180", 1.2, 1.3, "done")
            add_log("K18+040", 5.6, 5.5, "done")
            add_log("K12+180", 2.0, 5.1, "rejected")
        db.commit()
    finally:
        db.close()


ensure_schema()
seed()
start_claimer()


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(auth[7:].strip(), SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    sub = payload.get("sub")
    if sub not in USERS:
        return None
    return {"username": sub, "role": payload.get("role")}


def require_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


def require_writer(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify({"detail": "未登录"}), 401
        if user["role"] != "writer":
            return jsonify({"detail": "巡检员只读：能看配对和差值，不许改配对也不能报"}), 403
        g.user = user
        return fn(*args, **kwargs)

    return wrapper


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "tunnel-convergence-desk"})


@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    user = USERS.get(username)
    if not user or not pwd.verify(password, user["password_hash"]):
        return jsonify({"detail": "用户名或密码错误"}), 401
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    token = jwt.encode(
        {"sub": username, "role": user["role"], "exp": exp}, SECRET, algorithm="HS256"
    )
    return jsonify({"access_token": token, "username": username, "role": user["role"]})


@app.get("/api/logs")
@require_login
def list_logs():
    db = SessionLocal()
    try:
        rows = db.query(ConvergenceLog).order_by(ConvergenceLog.id.desc()).all()
        return jsonify([row_dict(r) for r in rows])
    finally:
        db.close()


@app.post("/api/logs")
@require_writer
def create_log():
    body = request.get_json(silent=True) or {}
    section = (body.get("section") or "").strip()
    if not section:
        return jsonify({"detail": "断面不能为空"}), 400
    try:
        left_mm = float(body.get("left_mm"))
        right_mm = float(body.get("right_mm"))
    except (TypeError, ValueError):
        return jsonify({"detail": "左右两路读数都必须是数字"}), 400
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        # 进队和配对冻结并进一次提交：行锁（NOWAIT）+ 同事务快照，
        # 两人同时抢同一配对至多成功一笔。
        pairing = (
            db.query(Pairing)
            .filter(Pairing.section == section)
            .with_for_update(nowait=True)
            .first()
        )
        if pairing is None:
            return jsonify({"detail": f"断面 {section} 未登记左右测缝计配对，对不上不许进队"}), 400
        reason = dual_reject_reason(left_mm, right_mm, pairing.threshold_mm)
        row = ConvergenceLog(
            section=section,
            left_mm=left_mm,
            right_mm=right_mm,
            diff_mm=dual_diff(left_mm, right_mm),
            status="rejected" if reason else "pending",
            reason=reason,
            pairing_id=pairing.id,
            pair_left_gauge=pairing.left_gauge,
            pair_right_gauge=pairing.right_gauge,
            pair_threshold_mm=pairing.threshold_mm,
            created_by=g.user["username"],
            created_at=now,
            processed_at=now if reason else None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        if reason:
            return jsonify({"detail": reason, "row": row_dict(row)}), 422
        return jsonify(row_dict(row)), 201
    except OperationalError:
        db.rollback()
        return jsonify({"detail": "同一配对正被另一笔提交抢占，至多成功一笔，请稍后重试"}), 409
    finally:
        db.close()


@app.get("/api/pairings")
@require_login
def list_pairings():
    db = SessionLocal()
    try:
        rows = db.query(Pairing).order_by(Pairing.id).all()
        return jsonify([pairing_dict(p) for p in rows])
    finally:
        db.close()


def _read_pairing_body(body, current=None):
    section = (body.get("section") or (current.section if current else "") or "").strip()
    left_gauge = (body.get("left_gauge") or (current.left_gauge if current else "") or "").strip()
    right_gauge = (body.get("right_gauge") or (current.right_gauge if current else "") or "").strip()
    raw_threshold = body.get("threshold_mm", current.threshold_mm if current else None)
    if not section or not left_gauge or not right_gauge:
        return None, (jsonify({"detail": "断面、左支编号、右支编号都不能为空"}), 400)
    if left_gauge == right_gauge:
        return None, (jsonify({"detail": "左右两支编号不能相同"}), 400)
    try:
        threshold_mm = float(raw_threshold)
    except (TypeError, ValueError):
        return None, (jsonify({"detail": "差值门槛必须是数字"}), 400)
    if threshold_mm <= 0:
        return None, (jsonify({"detail": "差值门槛必须大于 0"}), 400)
    return (section, left_gauge, right_gauge, threshold_mm), None


@app.post("/api/pairings")
@require_writer
def create_pairing():
    parsed, err = _read_pairing_body(request.get_json(silent=True) or {})
    if err:
        return err
    section, left_gauge, right_gauge, threshold_mm = parsed
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        p = Pairing(
            section=section,
            left_gauge=left_gauge,
            right_gauge=right_gauge,
            threshold_mm=threshold_mm,
            created_by=g.user["username"],
            created_at=now,
            updated_at=now,
        )
        db.add(p)
        # 断面唯一约束兜底：两人同时抢同一配对，至多成功一笔
        db.commit()
        db.refresh(p)
        return jsonify(pairing_dict(p)), 201
    except IntegrityError:
        db.rollback()
        return jsonify({"detail": f"断面 {section} 已登记左右配对，同一配对至多成功一笔"}), 409
    finally:
        db.close()


@app.put("/api/pairings/<int:pairing_id>")
@require_writer
def update_pairing(pairing_id):
    db = SessionLocal()
    try:
        p = db.get(Pairing, pairing_id)
        if p is None:
            return jsonify({"detail": "配对不存在"}), 404
        parsed, err = _read_pairing_body(request.get_json(silent=True) or {}, current=p)
        if err:
            return err
        p.section, p.left_gauge, p.right_gauge, p.threshold_mm = parsed
        p.updated_at = datetime.now(timezone.utc)
        # 只影响之后的新单；旧单配对随单冻结，不受登记表改动影响
        db.commit()
        db.refresh(p)
        return jsonify(pairing_dict(p))
    except IntegrityError:
        db.rollback()
        return jsonify({"detail": "该断面已登记左右配对"}), 409
    finally:
        db.close()
