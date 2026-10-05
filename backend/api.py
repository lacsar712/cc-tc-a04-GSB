import os
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError

from claimer import start as start_claimer
from models import (
    Base,
    ConvergenceLog,
    DualReport,
    Pairing,
    SessionLocal,
    dual_dict,
    engine,
    pairing_dict,
    row_dict,
)
from rules import diff_check

SECRET = os.environ.get("JWT_SECRET", "tunnelconv-dev-secret")
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
USERS = {
    "surveyor": {"role": "writer", "password_hash": pwd.hash("surv123456")},
    "inspector": {"role": "reader", "password_hash": pwd.hash("insp123456")},
}

app = Flask(__name__)


def seed():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(ConvergenceLog).count() > 0:
            return
        now = datetime.now(timezone.utc)
        for chainage, delta, expect in (("K12+180", 1.2, "合格"), ("K18+040", 5.6, "超限")):
            from rules import judge

            verdict, reason = judge(delta)
            assert verdict == expect
            db.add(
                ConvergenceLog(
                    chainage=chainage,
                    delta_mm=delta,
                    status="done",
                    verdict=verdict,
                    reason=reason,
                    created_by="surveyor",
                    created_at=now,
                    processed_at=now,
                )
            )
        db.commit()
    finally:
        db.close()


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


def require_writer(fn=None, *, message="仅测量员可提交收敛读数"):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"detail": "未登录"}), 401
            if user["role"] != "writer":
                return jsonify({"detail": message}), 403
            g.user = user
            return fn(*args, **kwargs)

        return wrapper

    return deco(fn) if fn is not None else deco


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
    chainage = (body.get("chainage") or "").strip()
    if not chainage:
        return jsonify({"detail": "桩号不能为空"}), 400
    try:
        delta_mm = float(body.get("delta_mm"))
    except (TypeError, ValueError):
        return jsonify({"detail": "收敛值必须是数字"}), 400
    db = SessionLocal()
    try:
        row = ConvergenceLog(
            chainage=chainage,
            delta_mm=delta_mm,
            status="pending",
            created_by=g.user["username"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(row_dict(row)), 201
    finally:
        db.close()


def _pairing_payload():
    body = request.get_json(silent=True) or {}
    section = (body.get("section") or "").strip()
    left_no = (body.get("left_no") or "").strip()
    right_no = (body.get("right_no") or "").strip()
    if not section:
        return None, (jsonify({"detail": "断面不能为空"}), 400)
    if not left_no:
        return None, (jsonify({"detail": "左支编号不能为空"}), 400)
    if not right_no:
        return None, (jsonify({"detail": "右支编号不能为空"}), 400)
    try:
        threshold_mm = float(body.get("threshold_mm"))
    except (TypeError, ValueError):
        return None, (jsonify({"detail": "差值门槛必须是数字"}), 400)
    if threshold_mm <= 0:
        return None, (jsonify({"detail": "差值门槛必须大于 0"}), 400)
    return (section, left_no, right_no, threshold_mm), None


@app.get("/api/pairings")
@require_login
def list_pairings():
    db = SessionLocal()
    try:
        rows = db.query(Pairing).order_by(Pairing.id).all()
        return jsonify([pairing_dict(r) for r in rows])
    finally:
        db.close()


@app.post("/api/pairings")
@require_writer(message="仅测量员可登记左右配对")
def create_pairing():
    payload, err = _pairing_payload()
    if err:
        return err
    section, left_no, right_no, threshold_mm = payload
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        row = Pairing(
            section=section,
            left_no=left_no,
            right_no=right_no,
            threshold_mm=threshold_mm,
            created_by=g.user["username"],
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # 断面唯一约束：两人同时抢同一配对，至多成功一笔
            return jsonify({"detail": f"断面 {section} 已登记左右配对"}), 409
        db.refresh(row)
        return jsonify(pairing_dict(row)), 201
    finally:
        db.close()


@app.put("/api/pairings/<int:pairing_id>")
@require_writer(message="仅测量员可修改左右配对")
def update_pairing(pairing_id):
    payload, err = _pairing_payload()
    if err:
        return err
    section, left_no, right_no, threshold_mm = payload
    db = SessionLocal()
    try:
        row = db.get(Pairing, pairing_id)
        if row is None:
            return jsonify({"detail": "配对不存在"}), 404
        row.section = section
        row.left_no = left_no
        row.right_no = right_no
        row.threshold_mm = threshold_mm
        row.updated_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return jsonify({"detail": f"断面 {section} 已登记左右配对"}), 409
        db.refresh(row)
        # 已上报的旧单保存冻结快照，不受本次修改影响
        return jsonify(pairing_dict(row))
    finally:
        db.close()


@app.get("/api/dual-reports")
@require_login
def list_dual_reports():
    db = SessionLocal()
    try:
        rows = db.query(DualReport).order_by(DualReport.id.desc()).all()
        return jsonify([dual_dict(r) for r in rows])
    finally:
        db.close()


@app.post("/api/dual-reports")
@require_writer
def create_dual_report():
    body = request.get_json(silent=True) or {}
    section = (body.get("section") or "").strip()
    if not section:
        return jsonify({"detail": "断面不能为空"}), 400
    try:
        left_mm = float(body.get("left_mm"))
        right_mm = float(body.get("right_mm"))
    except (TypeError, ValueError):
        return jsonify({"detail": "左右两路读数必须是数字"}), 400
    db = SessionLocal()
    try:
        # 进队与配对冻结并进一次提交：同一事务内锁定配对行、冻结快照、落单
        pairing = (
            db.query(Pairing)
            .filter(Pairing.section == section)
            .with_for_update()
            .first()
        )
        if pairing is None:
            return jsonify({"detail": f"断面 {section} 尚未登记左右配对，不许进队"}), 400
        diff_mm, reject_reason = diff_check(left_mm, right_mm, pairing.threshold_mm)
        row = DualReport(
            section=section,
            left_mm=left_mm,
            right_mm=right_mm,
            diff_mm=diff_mm,
            pairing_id=pairing.id,
            left_no=pairing.left_no,
            right_no=pairing.right_no,
            threshold_mm=pairing.threshold_mm,
            status="rejected" if reject_reason else "pending",
            verdict="双路超差" if reject_reason else None,
            reason=reject_reason,
            created_by=g.user["username"],
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return jsonify(dual_dict(row)), 201
    finally:
        db.close()
