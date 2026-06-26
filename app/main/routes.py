from flask import current_app, render_template
from tna_utilities.flask import cacheable_duration

from app.lib.aws import get_merlin_files_manifest
from app.main import bp


@bp.route("/")
def index():
    return render_template("main/index.html")


@bp.route("/merlin/")
@cacheable_duration(3600)
def merlin():
    try:
        manifest = get_merlin_files_manifest()
    except Exception as e:
        current_app.logger.critical(f"Error retrieving manifest: {e}")
        return render_template("errors/server.html"), 500
    return render_template("merlin/index.html", manifest=manifest)
