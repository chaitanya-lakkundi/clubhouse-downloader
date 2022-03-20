#!venv/bin/python

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class StatsModel(db.Model):
    __tablename__ = "Statistics"

    sid = db.Column(db.Integer(), autoincrement=True, primary_key=True)
    churl = db.Column(db.String())
    title = db.Column(db.String())
    room = db.Column(db.String())
    duration = db.Column(db.Integer())
    event_date = db.Column(db.DateTime(), nullable=True)
    chdir = db.Column(db.String())
    stage = db.Column(db.Integer())
    # percent complete
    pc = db.Column(db.Integer())
    status = db.Column(db.Integer())
    msg = db.Column(db.String())
    time_elapsed = db.Column(db.Integer())
    hidden = db.Column(db.Boolean())

    def __init__(self, churl, title="", room="", duration=0, event_date=None, chdir="", stage=0, pc=0, status=0, msg="", time_elapsed=0, hidden=False):
        self.churl = churl
        self.title = title
        self.room = room
        self.duration = duration
        self.event_date = event_date
        self.chdir = chdir
        self.stage = stage
        self.pc = pc
        self.status = status
        self.msg = msg
        self.time_elapsed = time_elapsed
        self.hidden = hidden