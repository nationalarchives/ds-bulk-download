import json
from builtins import UnicodeDecodeError

import boto3
from botocore.exceptions import (
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    NoRegionError,
    ParamValidationError,
)
from flask import current_app
from pydantic import ValidationError

from tasks.process import BatchManifest


class ManifestError(Exception):
    pass


def get_files_manifest(manifest_name: str) -> dict:
    """
    Returns a list of all files in the manifest.
    """

    try:
        s3_client = boto3.client(
            "s3",
            region_name=current_app.config.get("AWS_DEFAULT_REGION"),
            endpoint_url=current_app.config.get("S3_ENDPOINT", None),
        )
        content_object = s3_client.get_object(
            Bucket=current_app.config.get("S3_EXPORT_BUCKET"), Key=manifest_name
        )
    except (
        NoRegionError,
        ParamValidationError,
        ClientError,
        NoCredentialsError,
        EndpointConnectionError,
        ConnectTimeoutError,
    ) as e:
        raise ManifestError(f"Error retrieving manifest: {e!s}") from e

    try:
        file_content = content_object.get("Body").read().decode("utf-8")
    except UnicodeDecodeError as e:
        raise ManifestError(f"Error decoding manifest: {e!s}") from e

    try:
        json_content = json.loads(file_content)
    except json.JSONDecodeError as e:
        raise ManifestError(f"Error parsing manifest JSON: {e!s}") from e

    try:
        manifest = BatchManifest.validate(json_content).model_dump(mode="json")
    except ValidationError as e:
        raise ManifestError(f"Error validating manifest: {e!s}") from e

    try:
        manifest["items"] = [
            {
                **item,
                "size": s3_client.head_object(
                    Bucket=current_app.config.get("S3_EXPORT_BUCKET"), Key=item["file"]
                ).get("ContentLength", 0),
            }
            for item in manifest["items"]
        ]
    except (
        NoRegionError,
        ParamValidationError,
        ClientError,
        NoCredentialsError,
        EndpointConnectionError,
        ConnectTimeoutError,
    ) as e:
        raise ManifestError(f"Error retrieving file sizes: {e!s}") from e

    return manifest
