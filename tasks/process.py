import io
import json
import logging
import os
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Optional

import boto3
from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class BatchManifestItem(BaseModel):
    name: str
    size: int
    file_count: int
    created_timestamp: datetime = datetime.now()
    year: Optional[int] = None
    month: Optional[int] = None
    week: Optional[int] = None


class FileBatch(BaseModel):
    manifest_data: BatchManifestItem
    files: list[dict]


class Packager:
    manifest_name: Optional[str] = None
    package_name: str
    source: Optional[str] = None
    s3_client: Optional[boto3.client] = None

    def __init__(
        self,
        package_name: str,
        from_datetime: Optional[datetime] = None,
        to_datetime: Optional[datetime] = None,
    ):
        if not package_name:
            raise ValueError("package_name must be provided.")
        self.package_name = package_name
        self.files = []
        self.from_datetime = from_datetime
        self.to_datetime = to_datetime
        self.s3_export_bucket = os.environ.get("S3_EXPORT_BUCKET")
        if not self.s3_export_bucket:
            raise ValueError("S3_EXPORT_BUCKET environment variable is not set.")
        logger.debug(
            f"Packager initialized with from_datetime: {self.from_datetime}, to_datetime: {self.to_datetime}"
        )

    def _get_s3_client(self):
        if not self.s3_client:
            s3_endpoint = os.environ.get("S3_ENDPOINT", "")
            if not s3_endpoint:
                raise ValueError("S3_ENDPOINT environment variable is not set.")
            self.s3_client = boto3.client("s3", endpoint_url=s3_endpoint)
        return self.s3_client

    def scan(self, source=None):
        if source is None:
            raise ValueError("Source must be provided for scanning.")
        self.source = source
        logger.debug(f"Scanning source: {self.source}")
        s3_client = self._get_s3_client()
        self.files = s3_client.list_objects_v2(Bucket=self.source).get("Contents", [])
        if self.from_datetime and self.to_datetime:
            self.files = [
                file
                for file in self.files
                if self.from_datetime <= file["LastModified"] <= self.to_datetime
            ]
        elif self.from_datetime:
            self.files = [
                file
                for file in self.files
                if file["LastModified"] >= self.from_datetime
            ]
        elif self.to_datetime:
            self.files = [
                file for file in self.files if file["LastModified"] <= self.to_datetime
            ]

    def _chunk(self):
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.package_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
            ),
            files=self.files,
        )
        logger.debug(f"-- Created chunk with {len(chunk.files)} files")
        return [chunk]

    def _get_existing_manifest(self, manifest_name):
        logger.debug(f"Fetching existing manifest for: {manifest_name}")
        s3_client = self._get_s3_client()
        content_object = s3_client.get_object(
            Bucket=self.s3_export_bucket, Key=manifest_name
        )
        file_content = content_object.get("Body").read().decode("utf-8")
        logger.debug(f"-- Existing manifest content: {file_content}")
        json_content = json.loads(file_content)
        manifest_type = TypeAdapter(list[BatchManifestItem])
        return manifest_type.validate_python(json_content)

    def process(self, manifest_name=None, export_prefix=None):
        if not self.source:
            raise ValueError("Source must be provided for processing.")
        if manifest_name is None:
            raise ValueError("Manifest name must be provided for processing.")
        if export_prefix is None:
            raise ValueError("Export prefix must be provided for processing.")
        self.manifest_name = manifest_name
        self.export_prefix = export_prefix

        if not self.files:
            raise ValueError("No files to process. Try running scan() first.")

        existing_manifest = self._get_existing_manifest(
            f"{self.export_prefix}/{self.manifest_name}"
        )

        chunked_files = self._chunk()
        logger.debug(f"Processing {len(chunked_files)} chunks of files")
        for chunk in chunked_files:
            logger.debug(f"-- Chunk: {chunk.manifest_data}")
            for file in chunk.files:
                logger.debug(
                    f"---- File: {file['Key']} ({file['LastModified']}) - Size: {file['Size']} bytes"
                )
            self._zip_and_upload(chunk)

        self._post_process(existing_manifest, chunked_files)

    def _zip_and_upload(self, chunk):
        logger.debug(f"Zipping and uploading chunk: {chunk.manifest_data.name}")
        s3_client = self._get_s3_client()
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zipper:
            for file in chunk.files:
                logger.debug(f"-- Adding S3 file to ZIP: {self.source}/{file['Key']}")
                infile_object = s3_client.get_object(
                    Bucket=self.source, Key=file["Key"]
                )
                infile_content = infile_object["Body"].read()
                zipper.writestr(file["Key"], infile_content)
        s3_client.put_object(
            Bucket=self.s3_export_bucket,
            Key=f"{self.export_prefix}/{chunk.manifest_data.name}.zip",
            Body=zip_buffer.getvalue(),
        )

    def _generate_manifest_items(self, chunked_files):
        return [chunk.manifest_data.model_dump(mode="json") for chunk in chunked_files]

    def _manifest_items_to_remove(self, existing_manifest):
        return []

    def _post_process(self, existing_manifest, chunked_files):
        logger.debug("Post-processing tasks")
        items_to_remove = self._manifest_items_to_remove(existing_manifest)
        item_names_to_remove = [item.name for item in items_to_remove]
        logger.debug(f"-- Items to remove from manifest: {item_names_to_remove}")
        manifest_content_to_keep = [
            item.model_dump(mode="json")
            for item in existing_manifest
            if item.name not in item_names_to_remove
        ]
        new_manifest_content = self._generate_manifest_items(chunked_files)
        self._save_manifest(manifest_content_to_keep + new_manifest_content)

    def _save_manifest(self, manifest_content):
        logger.debug(f"Save manifest: {self.export_prefix}/{self.manifest_name}")
        manifest_json = json.dumps(manifest_content, indent=4)
        logger.debug(manifest_json)
        s3_client = self._get_s3_client()
        s3_client.put_object(
            Bucket=self.s3_export_bucket,
            Key=f"{self.export_prefix}/{self.manifest_name}",
            Body=manifest_json,
            ContentType="application/json",
        )


class ThisWeekPackager(Packager):
    def __init__(self):
        today_datetime = datetime.now(timezone.utc)
        from_datetime = (
            today_datetime - timedelta(days=today_datetime.weekday())
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        to_datetime = (
            today_datetime + timedelta(days=6 - today_datetime.weekday())
        ).replace(hour=23, minute=59, second=59, microsecond=999999)
        self.week_index = today_datetime.day // 7 + 1
        package_name = f"{today_datetime.strftime('%Y-%m')}-w{self.week_index}.zip"
        super().__init__(
            package_name=package_name,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    def _chunk(self):
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.package_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
                year=self.from_datetime.year,
                month=self.from_datetime.month,
                week=self.week_index,
            ),
            files=self.files,
        )
        return [chunk]

    def _manifest_items_to_remove(self, existing_manifest):
        return [
            item
            for item in existing_manifest
            if item.year == self.from_datetime.year
            and item.month == self.from_datetime.month
            and item.week == self.week_index
        ]


class AllWeeksThisMonthPackager(Packager):
    # TODO: Implement this packager to handle all weeks of the current month
    pass


class LastMonthPackager(Packager):
    def __init__(self):
        today_datetime = datetime.now(timezone.utc)
        if today_datetime.month == 1:
            return  # Skip processing for January as there is no last month in the same year
        last_month = today_datetime.replace(day=1) + timedelta(days=-1)
        from_datetime = datetime(
            last_month.year, last_month.month, 1, 0, 0, 0, 0, tzinfo=timezone.utc
        )
        to_datetime = datetime(
            last_month.year,
            last_month.month,
            (today_datetime.replace(day=1) - timedelta(days=1)).day,
            23,
            59,
            59,
            999999,
            tzinfo=timezone.utc,
        )
        package_name = f"{last_month.strftime('%Y-%m')}.zip"
        super().__init__(
            package_name=package_name,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    def _chunk(self):
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.package_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
                year=self.from_datetime.year,
                month=self.from_datetime.month,
            ),
            files=self.files,
        )
        return [chunk]

    def _manifest_items_to_remove(self, existing_manifest):
        return [
            item
            for item in existing_manifest
            if item.year == self.from_datetime.year
            and item.month == self.from_datetime.month
        ]


class LastYearPackager(Packager):
    def __init__(self):
        today_datetime = datetime.now()
        today_year = today_datetime.year
        yesteryear = today_year - 1
        from_datetime = datetime(yesteryear, 1, 1, 0, 0, 0, 0)
        to_datetime = datetime(yesteryear, 12, 31, 23, 59, 59, 999999)
        package_name = f"{yesteryear}.zip"
        super().__init__(
            package_name=package_name,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    def _chunk(self):
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.package_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
                year=self.from_datetime.year,
            ),
            files=self.files,
        )
        return [chunk]

    def _manifest_items_to_remove(self, existing_manifest):
        return [
            item for item in existing_manifest if item.year == self.from_datetime.year
        ]


class AllPackager(Packager):
    def __init__(self, *args, **kwargs):
        super().__init__(package_name="all.zip")

    def _manifest_items_to_remove(self, existing_manifest):
        return existing_manifest


class ChunkedPackager(AllPackager):
    def __init__(self, *args, **kwargs):
        self.chunk_size = int(args[0]) if args else 10
        super().__init__(package_name="all.zip")

    def _chunk(self):
        logger.debug(f"Chunking files into chunks of size: {self.chunk_size}")
        file_chunks = [
            self.files[i : i + self.chunk_size]
            for i in range(0, len(self.files), self.chunk_size)
        ]
        return [
            FileBatch(
                manifest_data=BatchManifestItem(
                    name=f"{self.package_name}_{i}",
                    size=sum(file["Size"] for file in chunk),
                    file_count=len(chunk),
                ),
                files=chunk,
            )
            for i, chunk in enumerate(file_chunks)
        ]


class Batch:
    packager_class = None
    source = None
    manifest_name = None
    prefix = None

    def __init__(self, packager_class, extra_args=None):
        self.packager_class = packager_class
        self.extra_args = extra_args or []

    def process(self):
        if not self.source:
            raise ValueError("No source has been defined for this batch.")
        if not self.manifest_name:
            raise ValueError("No manifest_name has been defined for this batch.")
        if not self.prefix:
            raise ValueError("No prefix has been defined for this batch.")
        packager = self.packager_class(*self.extra_args)
        packager.scan(self.source)
        packager.process(manifest_name=self.manifest_name, export_prefix=self.prefix)


class MerlinBatch(Batch):
    source = os.environ.get("S3_MERLIN_SOURCE", "")
    manifest_name = os.environ.get("S3_MANIFEST_NAME", "manifest.json")
    prefix = os.environ.get("S3_MERLIN_PREFIX", "merlin")


def main(args):
    batches = {
        "merlin": MerlinBatch,
    }
    packagers = {
        "last_year": LastYearPackager,
        "last_month": LastMonthPackager,
        "this_week": ThisWeekPackager,
        "all": AllPackager,
        "chunked": ChunkedPackager,
    }

    if len(args) < 1 or args[0] == "help":
        logger.debug("Usage: python process.py <batch> <packager>")
        logger.debug(f"  Available batches: {', '.join(batches.keys())}")
        logger.debug(f"  Available packagers: {', '.join(packagers.keys())}")
        return

    if len(args) < 1 or args[0] not in batches:
        logger.error("Please provide a batch as an argument.")
        logger.debug(f"Available batches: {', '.join(batches.keys())}")
        exit(1)
    if len(args) < 2 or args[1] not in packagers:
        logger.error("Please provide a packager as an argument.")
        logger.debug(f"Available packagers: {', '.join(packagers.keys())}")
        exit(1)
    extra_args = args[2:]
    logger.debug(f"Extra arguments: {extra_args}")

    batch_class = batches[args[0]]
    batch = batch_class(packager_class=packagers[args[1]], extra_args=extra_args)
    batch.process()


if __name__ == "__main__":
    main(sys.argv[1:])
