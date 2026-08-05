from flask import Blueprint, render_template, session

from .security import require_login

views_bp = Blueprint("views", __name__)


@views_bp.get("/login")
def login_page():
    if session.get("user_id"):
        return render_template("dashboard.html")
    return render_template("login.html")


@views_bp.get("/")
@require_login(api=False)
def dashboard():
    return render_template("dashboard.html")
