"""AI Research Center page routes — Phase 17.

Pages: /research, /ai_agent
Templates live in templates/research/
"""

from __future__ import annotations

from flask import Blueprint, current_app, render_template

bp = Blueprint("web_research", __name__)


@bp.route("/research")
def research() -> str:
    current_model = current_app.config.get("RESEARCH_MODEL", "agnes-2.0-flash")
    return render_template("research/research.html", current_model=current_model)


@bp.route("/ai_agent")
def ai_agent() -> str:
    return render_template("research/ai_agent.html")
