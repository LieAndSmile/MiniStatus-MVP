# app/routes/public.py

from flask import Blueprint, render_template, request, session
from app.utils.helpers import get_system_stats, get_system_identity, get_all_quick_links, get_public_holidays, generate_month_calendar
from datetime import date

public_bp = Blueprint('public', __name__)

@public_bp.route('/', methods=['GET', 'POST'])
def index():
    """Homepage dashboard"""
    system_stats = get_system_stats()
    system_identity = get_system_identity()
    quick_links = get_all_quick_links()

    # Calendar logic
    today = date.today()

    if request.method == 'POST' and request.form.get('country'):
        session['calendar_country'] = request.form['country']

    country = (
        request.form.get('country')
        or request.args.get('country')
        or session.get('calendar_country')
        or 'US'
    )
    holidays = get_public_holidays(today.year, country)
    calendar_weeks = generate_month_calendar(today.year, today.month, today, holidays)

    # List of countries (ISO codes and names)
    countries = [
        ('US', 'United States'),
        ('GB', 'United Kingdom'),
        ('DE', 'Germany'),
        ('FR', 'France'),
        ('RU', 'Russia'),
        ('UA', 'Ukraine'),
        ('PL', 'Poland'),
        ('IT', 'Italy'),
        ('ES', 'Spain'),
        ('JP', 'Japan'),
        ('CN', 'China'),
        ('IN', 'India'),
        # Add more as needed
    ]

    # --- Static GitHub Repos Panel ---
    github_repos = [
        {
            "name": "MiniStatus-MVP",
            "url": "https://github.com/LieAndSmile/MiniStatus-MVP",
            "description": "A lightweight, self-hosted service status dashboard."
        },
        # Add more repos here if needed
    ]

    return render_template('public/home.html',
                           system_stats=system_stats,
                           system_identity=system_identity,
                           quick_links=quick_links,
                           calendar_weeks=calendar_weeks,
                           today=today,
                           country=country,
                           countries=countries,
                           github_repos=github_repos)
