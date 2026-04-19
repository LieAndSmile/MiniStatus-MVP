"""Admin auth and settings — Polymarket operator console (Phase 5c Tier 3: no service monitor)."""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.extensions import limiter
from app.utils.password import verify_password, update_password_in_env
from app.utils.decorators import admin_required
import os
from dotenv import load_dotenv

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
def admin_root():
    if session.get("authenticated"):
        return redirect(url_for("polymarket.polymarket_scorecard"))
    return redirect(url_for("admin.login"))


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", error_message="Too many login attempts. Please wait a minute before trying again.")
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        stored_username = os.getenv("ADMIN_USERNAME")
        stored_password = os.getenv("ADMIN_PASSWORD")

        if username == stored_username and stored_password and verify_password(password, stored_password):
            session["authenticated"] = True
            flash("Successfully logged in!", "success")
            return redirect(url_for("polymarket.polymarket_scorecard"))
        flash("Invalid credentials. Please try again.", "error")

    return render_template("login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("authenticated", None)
    flash("Successfully logged out.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.route("/help")
@admin_required
def help_page():
    return render_template("admin/help.html")


@admin_bp.route("/change-password", methods=["GET", "POST"])
@admin_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not current_password or not new_password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("admin/change_password.html")

        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return render_template("admin/change_password.html")

        if len(new_password) < 6:
            flash("New password must be at least 6 characters long.", "error")
            return render_template("admin/change_password.html")

        stored_password = os.getenv("ADMIN_PASSWORD")
        if not stored_password or not verify_password(current_password, stored_password):
            flash("Current password is incorrect.", "error")
            return render_template("admin/change_password.html")

        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
        if update_password_in_env(env_path, new_password):
            load_dotenv(override=True)
            flash("Password changed successfully!", "success")
            return redirect(url_for("polymarket.polymarket_scorecard"))
        flash("Failed to update password. Please check file permissions.", "error")

    return render_template("admin/change_password.html")
