from flask import current_app, render_template
from tna_utilities.flask import cacheable_duration

from app.lib.aws import ManifestError, get_files_manifest
from app.main import bp


@bp.route("/")
def index():
    return render_template("main/index.html")


@bp.route("/merlin/")
@cacheable_duration(3600)
def merlin():
    manifest_name = f"{current_app.config.get('S3_EXPORT_PREFIX_MERLIN')}/{current_app.config.get('S3_MANIFEST_NAME')}"
    try:
        manifest = get_files_manifest(manifest_name)
    except ManifestError:
        current_app.logger.exception("Error retrieving manifest")
        return render_template("errors/server.html"), 500
    return render_template("merlin/index.html", manifest=manifest)
