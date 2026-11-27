"""Student-verification rules for the demo. SQLite connections are owned by store.py.

Call write helpers inside a locked_batch transaction. No delivery service is used.
The caller logs a generated code only after its transaction has committed.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta

from flask import current_app

from pooling import config
from store import Problem, issue_token, now


def university_json(row):
    return {key: row[key] for key in ("id", "name", "city", "campus", "gate")} | {
        "available": bool(row["available"]),
    }


def university(db, university_id):
    row = db.execute("SELECT * FROM universities WHERE id = ?", (university_id,)).fetchone()
    if row is None:
        raise Problem("university_not_found", "No such university.", 404)
    return row


def public_student(db, student_id):
    if student_id is None:
        return None
    row = db.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"], "firstName": row["first_name"], "verified": row["verified_at"] is not None,
        "verifiedAt": row["verified_at"], "university": university_json(university(db, row["university"])),
        # Demo Jeeny profile gender: decides whether "Men only" or "Women only" is offered
        "gender": row["gender"],
    }


def booking_identity(db, token):
    """(name, student_key, gender) for a booking by this student token, from its verified profile.

    Raises 403 verification_required for a token without a verified student.
    """
    student = public_student(db, token["student_id"])
    if not student or not student["verified"]:
        raise Problem("verification_required", "Verify your university email before booking a ride.", 403)
    return student["firstName"], f"student:{student['id']}", student["gender"]


def search_universities(db, search):
    term = search.strip()
    if len(term) > config.UNIVERSITY_SEARCH_MAX:
        raise Problem("invalid_input", "University search is too long.", 400)
    # instr treats '%' and '_' as text, not SQL wildcard expressions.
    return [university_json(row) for row in db.execute(
        "SELECT * FROM universities WHERE instr(lower(name || ' ' || city || ' ' || campus), lower(?)) > 0 "
        "ORDER BY available DESC, name", (term,),
    )]


def _digest(token_hash, nonce, code):
    key = current_app.config["SECRET_KEY"]
    if isinstance(key, str):
        key = key.encode()
    return hmac.new(key, f"{token_hash}:{nonce}:{code}".encode(), hashlib.sha256).hexdigest()


def _matches(challenge, code):
    return hmac.compare_digest(
        challenge["code_digest"], _digest(challenge["token_hash"], challenge["nonce"], code),
    )


def _existing_challenge(db, token_hash):
    return db.execute("SELECT * FROM verification_challenges WHERE token_hash = ?", (token_hash,)).fetchone()


def _resend_ready(challenge, at):
    if challenge and at < datetime.fromisoformat(challenge["sent_at"]) + timedelta(seconds=config.VERIFY_RESEND_SEC):
        raise Problem("verification_resend_too_soon",
                      f"Wait {config.VERIFY_RESEND_SEC} seconds before requesting a new code.", 429)


def _new_challenge(db, token_hash, student_id, old, at):
    _resend_ready(old, at)
    limit = 10 ** config.VERIFY_CODE_DIGITS
    number = secrets.randbelow(limit)
    code = f"{number:0{config.VERIFY_CODE_DIGITS}d}"
    if old and _matches(old, code):
        code = f"{(number + 1) % limit:0{config.VERIFY_CODE_DIGITS}d}"
    nonce = secrets.token_hex(16)
    expires = at + timedelta(minutes=config.VERIFY_CODE_MIN)
    db.execute(
        "INSERT INTO verification_challenges "
        "(token_hash, student_id, code_digest, nonce, expires_at, sent_at, wrong_attempts) VALUES (?, ?, ?, ?, ?, ?, 0) "
        "ON CONFLICT(token_hash) DO UPDATE SET student_id=excluded.student_id, code_digest=excluded.code_digest, "
        "nonce=excluded.nonce, expires_at=excluded.expires_at, sent_at=excluded.sent_at, wrong_attempts=0",
        (token_hash, student_id, _digest(token_hash, nonce, code), nonce, expires.isoformat(), at.isoformat()),
    )
    return code, {
        "expiresAt": expires.isoformat(),
        "resendAvailableAt": (at + timedelta(seconds=config.VERIFY_RESEND_SEC)).isoformat(),
    }


def _masked(email):
    local, domain = email.rsplit("@", 1)
    return f"{local[0]}***@{domain}"


def start_verification(db, token, university_id, email, first_name=None):
    school = university(db, university_id)
    if not school["available"]:
        raise Problem("campus_unavailable", "Yalla Ride is not available at this campus yet.", 409)
    email = email.strip().casefold()
    if len(email) > config.STUDENT_EMAIL_MAX or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise Problem("email_not_university", "Use your university email address.", 400)
    local, domain = email.rsplit("@", 1)
    if domain != school["email_domain"].casefold():
        raise Problem("email_not_university", "That email does not match the selected university.", 400)
    if first_name is None:
        prefix = re.split(r"[._+\-\d]", local, maxsplit=1)[0]
        first_name = prefix.title() or "Student"
    else:
        first_name = first_name.strip().split()[0] if first_name.strip() else ""
    if not first_name or len(first_name) > config.STUDENT_FIRST_NAME_MAX:
        raise Problem("invalid_input", "Enter a valid first name.", 400)
    student = db.execute(
        "SELECT * FROM students WHERE university = ? AND email = ?", (school["id"], email),
    ).fetchone()
    if student and token["student_id"] == student["id"] and student["verified_at"]:
        return None, {"alreadyVerified": True, "nextScreen": "05", "student": public_student(db, student["id"])}
    old = _existing_challenge(db, token["token_hash"])
    _resend_ready(old, now())
    if student is None:
        student_id = db.execute(
            "INSERT INTO students (university, email, first_name, gender) VALUES (?, ?, ?, ?)",
            (school["id"], email, first_name, config.DEMO_STUDENT_GENDER),
        ).lastrowid
    else:
        student_id = student["id"]
    code, body = _new_challenge(db, token["token_hash"], student_id, old, now())
    return (email, code), {**body, "maskedEmail": _masked(email), "delivery": "console_demo"}


def resend_verification(db, token):
    challenge = _existing_challenge(db, token["token_hash"])
    if challenge is None:
        raise Problem("verification_not_started", "Start student verification first.", 409)
    student = db.execute("SELECT * FROM students WHERE id = ?", (challenge["student_id"],)).fetchone()
    if not university(db, student["university"])["available"]:
        raise Problem("campus_unavailable", "Yalla Ride is not available at this campus yet.", 409)
    code, body = _new_challenge(db, token["token_hash"], student["id"], challenge, now())
    return (student["email"], code), {**body, "maskedEmail": _masked(student["email"]),
                                    "delivery": "console_demo", "message": "New code sent"}


def confirm_verification(db, token, code):
    """Return a public result or Problem. Wrong-attempt updates must COMMIT before an error is raised."""
    challenge = _existing_challenge(db, token["token_hash"])
    if challenge is None:
        return Problem("verification_not_started", "Start student verification first.", 409)
    if now() >= datetime.fromisoformat(challenge["expires_at"]):
        return Problem("verification_code_expired", "The code expired. Request a new one.", 410)
    if challenge["wrong_attempts"] >= config.VERIFY_MAX_WRONG:
        return Problem("verification_locked", "Too many incorrect codes. Request a new code.", 429)
    if not re.fullmatch(rf"\d{{{config.VERIFY_CODE_DIGITS}}}", code) or not _matches(challenge, code):
        db.execute("UPDATE verification_challenges SET wrong_attempts = wrong_attempts + 1 WHERE token_hash = ?",
                   (token["token_hash"],))
        return Problem("verification_code_invalid", "That code is incorrect.", 400)
    student = db.execute("SELECT * FROM students WHERE id = ?", (challenge["student_id"],)).fetchone()
    if not university(db, student["university"])["available"]:
        return Problem("campus_unavailable", "Yalla Ride is not available at this campus yet.", 409)
    db.execute("UPDATE students SET verified_at = COALESCE(verified_at, ?) WHERE id = ?",
               (now().isoformat(), student["id"]))
    db.execute("UPDATE api_tokens SET student_id = ? WHERE token_hash = ?", (student["id"], token["token_hash"]))
    db.execute("DELETE FROM verification_challenges WHERE token_hash = ?", (token["token_hash"],))
    new_token = issue_token(db, token["batch"], "student", student_id=student["id"], commit=False)
    return {
        "token": new_token, "tokenType": "Bearer", "nextScreen": "05",
        "student": public_student(db, student["id"]),
    }


def request_notification(db, token, university_id):
    school = university(db, university_id)
    if school["available"]:
        raise Problem("campus_available", "This campus is already available. You can verify now.", 409)
    db.execute(
        "INSERT OR IGNORE INTO university_notifications (university_id, token_hash, requested_at) VALUES (?, ?, ?)",
        (school["id"], token["token_hash"], now().isoformat()),
    )
    return {"university": university_json(school), "notificationRequested": True, "message": "We'll keep you posted"}
