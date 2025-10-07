from flask import Blueprint, render_template, request

bp = Blueprint("feedback", __name__)

@bp.route("/feedback", methods=["GET", "POST"])
def feedback_page():
    # No database needed; on POST just log to console and re-render the same page.
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        print(f"[Feedback] name={name!r} email={email!r} message={message!r}")
        # You can later add email sending or persist to DB if desired.
    return render_template("feedback.html")
