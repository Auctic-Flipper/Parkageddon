from flask import Blueprint, render_template

# Main site pages (home)
bp = Blueprint("home", __name__)

@bp.route("/")
def index():
    # Renders dashboard/index.html via Flask's template_folder setting
    return render_template("index.html")
