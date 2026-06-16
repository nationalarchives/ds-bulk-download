import json
from typing import Optional

# from flask import current_app
# import boto3
from pydantic import BaseModel, ConfigDict, TypeAdapter


class MerlinArchive(BaseModel):
    model_config = ConfigDict(strict=True)
    year: int
    month: int
    week: Optional[int] = None
    zip_filename: str
    zip_size_bytes: int
    file_count: int
    created_timestamp: str


def get_merlin_files_manifest():
    """
    Returns a list of all files in the Merlin directory.
    """

    # if not current_app.config["S3_BUCKET_NAME"] or not current_app.config["S3_MANIFEST_FILENAME"]:
    #     raise ValueError("S3_BUCKET_NAME and S3_MANIFEST_FILENAME must be set in the config.")

    file_list_adapter = TypeAdapter(list[MerlinArchive])

    # TODO: Link up to S3 and get the JSON manifest
    # s3 = boto3.resource("s3")
    # content_object = s3.Object(current_app.config["S3_BUCKET_NAME"], current_app.config["S3_MANIFEST_FILENAME"])
    # file_content = content_object.get()["Body"].read().decode("utf-8")
    # file_list_adapter.validate_json(file_content)
    # json_data = json.loads(file_content)
    json_data = [
        {
            "year": 2025,
            "month": 10,
            "zip_filename": "s3://ds-bulk-transfer-live/2025-10.zip",
            "zip_size_bytes": 4375616,
            "file_count": 1588,
            "created_timestamp": "2026-06-12T09:29:24.152065",
        },
        {
            "year": 2025,
            "month": 11,
            "zip_filename": "s3://ds-bulk-transfer-live/2025-11.zip",
            "zip_size_bytes": 1852823,
            "file_count": 1941,
            "created_timestamp": "2026-06-12T09:33:24.155453",
        },
        {
            "year": 2026,
            "month": 1,
            "zip_filename": "s3://ds-bulk-transfer-live/2026-01.zip",
            "zip_size_bytes": 707393,
            "file_count": 3000,
            "created_timestamp": "2026-06-12T09:35:24.159931",
        },
        {
            "year": 2025,
            "month": 12,
            "zip_filename": "s3://ds-bulk-transfer-live/2025-12.zip",
            "zip_size_bytes": 187535,
            "file_count": 1500,
            "created_timestamp": "2026-06-12T09:36:24.161073",
        },
        {
            "year": 2026,
            "month": 6,
            "week": 1,
            "zip_filename": "s3://ds-bulk-transfer-live/2026-06-week1.zip",
            "zip_size_bytes": 560398,
            "file_count": 527,
            "created_timestamp": "2026-06-12T09:38:24.162022",
        },
        {
            "year": 2026,
            "month": 6,
            "week": 2,
            "zip_filename": "s3://ds-bulk-transfer-live/2026-06-week2.zip",
            "zip_size_bytes": 122164,
            "file_count": 500,
            "created_timestamp": "2026-06-12T09:38:24.162022",
        },
        {
            "year": 2026,
            "month": 4,
            "zip_filename": "s3://ds-bulk-transfer-live/2026-04.zip",
            "zip_size_bytes": 8018293,
            "file_count": 2774,
            "created_timestamp": "2026-06-12T09:55:24.162674",
        },
        {
            "year": 2026,
            "month": 3,
            "zip_filename": "s3://ds-bulk-transfer-live/2026-03.zip",
            "zip_size_bytes": 4129378,
            "file_count": 5079,
            "created_timestamp": "2026-06-12T10:05:24.163364",
        },
        {
            "year": 2026,
            "month": 2,
            "zip_filename": "s3://ds-bulk-transfer-live/2026-02.zip",
            "zip_size_bytes": 907408,
            "file_count": 3999,
            "created_timestamp": "2026-06-12T10:08:24.164380",
        },
        {
            "year": 2026,
            "month": 5,
            "zip_filename": "s3://ds-bulk-transfer-live/2026-05.zip",
            "zip_size_bytes": 1014061,
            "file_count": 2252,
            "created_timestamp": "2026-06-12T10:11:24.165248",
        },
        {
            "year": 2025,
            "month": 9,
            "zip_filename": "s3://ds-bulk-transfer-live/2025-09.zip",
            "zip_size_bytes": 452205,
            "file_count": 250,
            "created_timestamp": "2026-06-12T10:02:24.166143",
        },
    ]

    file_list_adapter.validate_json(json.dumps(json_data))

    return json_data
