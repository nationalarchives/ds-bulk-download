import json

import boto3
from flask import current_app
from pydantic import TypeAdapter

from tasks.process import BatchManifestItem


def get_merlin_files_manifest():
    """
    Returns a list of all files in the Merlin directory.
    """

    s3_endpoint = current_app.config.get("S3_ENDPOINT")
    if not s3_endpoint:
        raise ValueError("S3_ENDPOINT environment variable is not set.")
    s3_client = boto3.client("s3", endpoint_url=s3_endpoint)
    manifest_name = f"{current_app.config.get('S3_MERLIN_PREFIX')}/{current_app.config.get('S3_MANIFEST_NAME')}"
    content_object = s3_client.get_object(
        Bucket=current_app.config.get("S3_EXPORT_BUCKET"), Key=manifest_name
    )

    file_content = content_object.get("Body").read().decode("utf-8")
    json_content = json.loads(file_content)
    downloads = TypeAdapter(list[BatchManifestItem])
    downloads.validate_json(json.dumps(json_content))

    json_content.sort(
        key=lambda x: (x["year"], x["month"] or 0, x["week"] or 0), reverse=True
    )

    return json_content
