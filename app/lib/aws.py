import json

# from flask import current_app
# import boto3
from pydantic import TypeAdapter

from tasks.process import BatchManifestItem


def get_merlin_files_manifest():
    """
    Returns a list of all files in the Merlin directory.
    """

    downloads = TypeAdapter(list[BatchManifestItem])

    # TODO: Link up to S3 and get the JSON manifest
    # s3 = boto3.resource("s3")
    # content_object = s3.Object(current_app.config["S3_BUCKET_NAME"], current_app.config["S3_MANIFEST_FILENAME"])
    # file_content = content_object.get()["Body"].read().decode("utf-8")
    # downloads.validate_json(file_content)
    # json_data = json.loads(file_content)
    json_data = [
        {
            "name": "2025",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2025,
            "month": None,
            "week": None,
        },
        {
            "name": "2025-11",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2025,
            "month": 11,
            "week": None,
        },
        {
            "name": "2026-02",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2026,
            "month": 2,
            "week": None,
        },
        {
            "name": "2026-04",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2026,
            "month": 4,
            "week": None,
        },
        {
            "name": "2026-05-w1",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2026,
            "month": 5,
            "week": 1,
        },
        {
            "name": "2026-05-w2",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2026,
            "month": 5,
            "week": 2,
        },
        {
            "name": "2026-05-w3",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2026,
            "month": 5,
            "week": 3,
        },
        {
            "name": "2026-05-w4",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2026,
            "month": 5,
            "week": 4,
        },
        {
            "name": "2026-05",
            "size": 128,
            "file_count": 1,
            "created_timestamp": "2025-01-01T00:00:00",
            "year": 2026,
            "month": 5,
            "week": None,
        },
        {
            "name": "2026-06-w3",
            "size": 62914560,
            "file_count": 4,
            "created_timestamp": "2026-06-18T13:47:27.398061",
            "year": 2026,
            "month": 6,
            "week": 3,
        },
    ]
    downloads.validate_json(json.dumps(json_data))

    json_data.sort(
        key=lambda x: (x["year"], x["month"] or 0, x["week"] or 0), reverse=True
    )

    return json_data
