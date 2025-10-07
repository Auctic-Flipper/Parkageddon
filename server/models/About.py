from flask import Blueprint, render_template

bp = Blueprint("about", __name__)

@bp.route("/about")
def about_page():
    return render_template("about.html")
