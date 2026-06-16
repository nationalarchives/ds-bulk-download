from flask import Blueprint

bp = Blueprint("merlin", __name__)

from app.merlin import routes  # noqa: E402,F401
