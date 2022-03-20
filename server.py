#!venv/bin/python

from flask import Flask, render_template, request, redirect
from models import StatsModel, db
from chdl import download_ch_audio

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chdl_stats.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


@app.before_first_request
def create_table():
    db.create_all()


@app.route("/", methods=["GET", "POST", "DELETE"])
def home():
    if request.method == "POST":
        churl = request.form["churl"].split("?")[0].strip()
        if churl:
            stats = StatsModel(churl=churl)
            download_ch_audio(churl, db_conn=db, db_inst=stats, db_model=StatsModel)

    if request.method == "DELETE":
        print(dict(request.form.items()))
        sid = request.form["sid"]
        sm = StatsModel.query.filter_by(sid=sid).first()
        sm.hidden = True
        db.session.add(sm)
        db.session.commit()
        return ""

    all_stats = StatsModel.query.filter_by(hidden=False).order_by(StatsModel.sid.desc())
    return render_template("home.html", all_stats=all_stats)


@app.route("/s/<int:sid>/<string:field>", methods=["GET"])
def status(sid, field):
    sm = StatsModel.query.filter_by(sid=sid).first()
    if field == "stage":
        return "🟦 " * sm.stage
    elif field == "pc":
        return sm.pc
    elif field == "status":
        r = {0: "🟨", 1: "🟩", 2: "🟥"}
        return r[sm.status] + " " + sm.msg
    elif field == "progress":
        p = """
        <div class="progress-bar progress-bar-striped {1}" role="progressbar" style="width: {0}%; aria-valuenow="{0}" aria-valuemin="0" aria-valuemax="100">{0}%</div>
        """.format(
            sm.pc, "progress-bar-animated" if sm.status == 0 else "bg-secondary"
        )
        return p


if __name__ == "__main__":
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.run(host="localhost", port=9020, debug=True)
