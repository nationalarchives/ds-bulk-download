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
    created_timestamp: datetime
    year: Optional[int] = None
    month: Optional[int] = None
    week: Optional[int] = None


class BatchManifest(BaseModel):
    packager: str
    packager_group: str
    updated: datetime = datetime.now()
    items: list[BatchManifestItem]


class FileBatch(BaseModel):
    manifest_data: BatchManifestItem
    files: list[dict]


class Packager:
    packager_name: Optional[str] = None
    packager_group: Optional[str] = None
    manifest_name: Optional[str] = None
    export_name: str
    source: Optional[str] = None
    s3_client: Optional[boto3.client] = None
    scanned: bool

    def __init__(
        self,
        export_name: str,
        from_datetime: Optional[datetime] = None,
        to_datetime: Optional[datetime] = None,
    ):
        if not self.packager_name:
            raise ValueError(
                "You cannot instantiate the base Packager class directly. Please use a subclass."
            )
        if not export_name:
            raise ValueError("export_name must be provided.")
        self.export_name = export_name
        self.files = []
        self.scanned = False
        self.from_datetime = from_datetime
        self.to_datetime = to_datetime
        self.s3_export_bucket = os.environ.get("S3_EXPORT_BUCKET")
        if not self.s3_export_bucket:
            raise ValueError("S3_EXPORT_BUCKET environment variable is not set.")
        logger.debug(
            f"Packager initialized with from_datetime: {self.from_datetime}, to_datetime: {self.to_datetime}"
        )

    def _get_s3_client(self) -> boto3.client:
        if not self.s3_client:
            s3_endpoint = os.environ.get("S3_ENDPOINT", "")
            if not s3_endpoint:
                raise ValueError("S3_ENDPOINT environment variable is not set.")
            self.s3_client = boto3.client("s3", endpoint_url=s3_endpoint)
        return self.s3_client

    def _get_all_s3_objects(self, **base_kwargs) -> list[dict]:
        s3_client = self._get_s3_client()
        continuation_token = None
        while True:
            list_kwargs = dict(MaxKeys=1000, **base_kwargs)
            if continuation_token:
                list_kwargs["ContinuationToken"] = continuation_token
            response = s3_client.list_objects_v2(**list_kwargs)
            yield from response.get("Contents", [])
            if not response.get("IsTruncated"):  # At the end of the list?
                break
            continuation_token = response.get("NextContinuationToken")

    def scan(self, source: str = None) -> None:
        if source is None:
            raise ValueError("Source must be provided for scanning.")
        self.source = source
        logger.debug(f"Scanning source: {self.source}")
        self.files = list(self._get_all_s3_objects(Bucket=self.source))
        logger.debug(f"-- Found {len(self.files)} total files in source")
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
        self.scanned = True
        logger.debug(f"-- Found {len(self.files)} files after filtering by date range")

    def _chunk(self) -> list[FileBatch]:
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.export_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
                created_timestamp=datetime.now(timezone.utc),
            ),
            files=self.files,
        )
        logger.debug(f"-- Created chunk with {len(chunk.files)} files")
        return [chunk]

    def _get_existing_manifest(self, manifest_name: str) -> BatchManifest:
        logger.debug(f"Fetching existing manifest for: {manifest_name}")
        s3_client = self._get_s3_client()
        try:
            content_object = s3_client.get_object(
                Bucket=self.s3_export_bucket, Key=manifest_name
            )
            file_content = content_object.get("Body").read().decode("utf-8")
        except s3_client.exceptions.NoSuchKey:
            logger.debug(f"-- No existing manifest found for: {manifest_name}")
            return BatchManifest(
                packager=self.packager_name,
                packager_group=self.packager_group,
                items=[],
            )
        logger.debug(f"-- Existing manifest content: {file_content}")
        json_content = json.loads(file_content)
        items = TypeAdapter(list[BatchManifestItem]).validate_python(
            json_content["items"]
        )
        return BatchManifest(
            packager=json_content["packager"],
            packager_group=json_content["packager_group"],
            items=items,
        )

    def process(
        self, manifest_name: str | None = None, export_prefix: str | None = None
    ) -> None:
        if not self.source:
            raise ValueError("Source must be provided for processing.")
        if manifest_name is None:
            raise ValueError("Manifest name must be provided for processing.")
        if export_prefix is None:
            raise ValueError("Export prefix must be provided for processing.")
        self.manifest_name = manifest_name
        self.export_prefix = export_prefix

        if not self.scanned:
            raise ValueError("No files to process. Try running scan() first.")
        if not self.files:
            logger.debug("No files to process after scanning. Exiting.")
            return

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

    def _zip_and_upload(self, chunk: FileBatch) -> None:
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
            Key=f"{self.export_prefix}/{chunk.manifest_data.name}",
            Body=zip_buffer.getvalue(),
        )

    def _generate_manifest_items(self, chunked_files: list[FileBatch]) -> list[dict]:
        return [chunk.manifest_data.model_dump(mode="json") for chunk in chunked_files]

    def _manifest_items_to_remove(
        self, existing_manifest_items: list[BatchManifestItem]
    ) -> list[BatchManifestItem]:
        return []

    def _post_process(
        self, existing_manifest: BatchManifest, chunked_files: list[FileBatch]
    ) -> None:
        logger.debug("Post-processing tasks")
        if existing_manifest.packager_group == self.packager_group:
            items_to_remove = self._manifest_items_to_remove(existing_manifest.items)
            item_names_to_remove = [item.name for item in items_to_remove]
            logger.debug(f"-- Items to remove from manifest: {item_names_to_remove}")
            items_to_keep = [
                item.model_dump(mode="json")
                for item in existing_manifest.items
                if item.name not in item_names_to_remove
            ]
        else:
            logger.debug(
                f"-- Removing all items from existing manifest due to packager group mismatch ({existing_manifest.packager_group} != {self.packager_group})"
            )
            items_to_keep = []
        new_items = self._generate_manifest_items(chunked_files)
        new_manifest = BatchManifest(
            packager=self.packager_name,
            packager_group=self.packager_group,
            items=items_to_keep + new_items,
        ).model_dump(mode="json")
        self._save_manifest(new_manifest)

    def _save_manifest(self, manifest_content: dict) -> None:
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
    packager_name = "this_week"
    packager_group = "by_date"

    def __init__(self):
        today_datetime = datetime.now(timezone.utc)
        from_datetime = (
            today_datetime - timedelta(days=today_datetime.weekday())
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        to_datetime = (
            today_datetime + timedelta(days=6 - today_datetime.weekday())
        ).replace(hour=23, minute=59, second=59, microsecond=999999)
        mondays_this_month = [
            (today_datetime.replace(day=1) + timedelta(days=i)).date()
            for i in range(today_datetime.day)
            if (today_datetime.replace(day=1) + timedelta(days=i)).weekday() == 0
        ]
        self.week_index = len(mondays_this_month)
        if today_datetime.replace(day=1).weekday() != 0:
            self.week_index += 1
        export_name = f"{today_datetime.strftime('%Y-%m')}-w{self.week_index}.zip"
        super().__init__(
            export_name=export_name,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    def _chunk(self) -> list[FileBatch]:
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.export_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
                year=self.from_datetime.year,
                month=self.from_datetime.month,
                week=self.week_index,
                created_timestamp=datetime.now(timezone.utc),
            ),
            files=self.files,
        )
        return [chunk]

    def _manifest_items_to_remove(
        self, existing_manifest_items: list[BatchManifestItem]
    ) -> list[BatchManifestItem]:
        return [
            item
            for item in existing_manifest_items
            if item.year == self.from_datetime.year
            and item.month == self.from_datetime.month
            and item.week == self.week_index
        ]


class AllWeeksThisMonthPackager(Packager):
    packager_name = "all_weeks_this_month"
    packager_group = "by_date"

    # TODO: Implement this packager to handle all weeks of the current month
    def __init__(self):
        today_datetime = datetime.now(timezone.utc)
        from_datetime = today_datetime.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        export_name_prefix = f"{today_datetime.strftime('%Y-%m')}"
        super().__init__(
            export_name=export_name_prefix,
            from_datetime=from_datetime,
            to_datetime=today_datetime,
        )
        raise NotImplementedError("AllWeeksThisMonthPackager is not yet implemented.")


class LastMonthPackager(Packager):
    packager_name = "last_month"
    packager_group = "by_date"

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
        export_name = f"{last_month.strftime('%Y-%m')}.zip"
        super().__init__(
            export_name=export_name,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    def _chunk(self) -> list[FileBatch]:
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.export_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
                year=self.from_datetime.year,
                month=self.from_datetime.month,
                created_timestamp=datetime.now(timezone.utc),
            ),
            files=self.files,
        )
        return [chunk]

    def _manifest_items_to_remove(
        self, existing_manifest_items: list[BatchManifestItem]
    ) -> list[BatchManifestItem]:
        return [
            item
            for item in existing_manifest_items
            if item.year == self.from_datetime.year
            and item.month == self.from_datetime.month
        ]


class LastYearPackager(Packager):
    packager_name = "last_year"
    packager_group = "by_date"

    def __init__(self):
        today_datetime = datetime.now(timezone.utc)
        today_year = today_datetime.year
        yesteryear = today_year - 1
        from_datetime = datetime(yesteryear, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
        to_datetime = datetime(
            yesteryear, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc
        )
        export_name = f"{yesteryear}.zip"
        super().__init__(
            export_name=export_name,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )

    def _chunk(self) -> list[FileBatch]:
        logger.debug("Chunking files")
        chunk = FileBatch(
            manifest_data=BatchManifestItem(
                name=self.export_name,
                size=sum(file["Size"] for file in self.files),
                file_count=len(self.files),
                year=self.from_datetime.year,
                created_timestamp=datetime.now(timezone.utc),
            ),
            files=self.files,
        )
        return [chunk]

    def _manifest_items_to_remove(
        self, existing_manifest_items: list[BatchManifestItem]
    ) -> list[BatchManifestItem]:
        return [
            item
            for item in existing_manifest_items
            if item.year == self.from_datetime.year
        ]


class AllPackager(Packager):
    packager_name = "all"
    packager_group = "all"

    def __init__(self, *args, **kwargs):
        super().__init__(export_name="all.zip")

    def _manifest_items_to_remove(
        self, existing_manifest_items: list[BatchManifestItem]
    ) -> list[BatchManifestItem]:
        return existing_manifest_items


class ChunkedPackager(AllPackager):
    packager_name = "chunked"
    packager_group = "chunked"

    def __init__(self, *args, **kwargs):
        self.chunk_size = int(args[0]) if args else 10
        super().__init__(export_name="all.zip")

    def _chunk(self) -> list[FileBatch]:
        logger.debug(f"Chunking files into chunks of size: {self.chunk_size}")
        file_chunks = [
            self.files[i : i + self.chunk_size]
            for i in range(0, len(self.files), self.chunk_size)
        ]
        return [
            FileBatch(
                manifest_data=BatchManifestItem(
                    name=f"{self.export_name}_{i}",
                    size=sum(file["Size"] for file in chunk),
                    file_count=len(chunk),
                    created_timestamp=datetime.now(timezone.utc),
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

    def __init__(self, packager_class: type[Packager], extra_args: list[str] = None):
        self.packager_class = packager_class
        self.extra_args = extra_args or []

    def process(self) -> None:
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


def main(args: list[str]) -> None:
    batches = {
        "merlin": MerlinBatch,
    }
    packagers = {
        LastYearPackager.packager_name: LastYearPackager,
        LastMonthPackager.packager_name: LastMonthPackager,
        ThisWeekPackager.packager_name: ThisWeekPackager,
        AllWeeksThisMonthPackager.packager_name: AllWeeksThisMonthPackager,
        AllPackager.packager_name: AllPackager,
        ChunkedPackager.packager_name: ChunkedPackager,
    }

    if len(args) < 1 or args[0] == "help":
        logger.debug("Usage: python process.py <batch> <packager>")
        logger.debug(f"  Available batches: {', '.join(batches.keys())}")
        logger.debug(f"  Available packagers: {', '.join(packagers.keys())}")
        return

    if len(args) < 1 or args[0] not in batches:
        logger.error("Please provide a batch as an argument.")
        logger.debug(f"Available batches: {', '.join(batches.keys())}")
        sys.exit(1)
    if len(args) < 2 or args[1] not in packagers:
        logger.error("Please provide a packager as an argument.")
        logger.debug(f"Available packagers: {', '.join(packagers.keys())}")
        sys.exit(1)
    extra_args = args[2:]
    logger.debug(f"Extra arguments: {extra_args}")

    batch_class = batches[args[0]]
    batch = batch_class(packager_class=packagers[args[1]], extra_args=extra_args)
    batch.process()


if __name__ == "__main__":
    main(sys.argv[1:])


def lambda_handler(event, context):
    batch = event["Batch"]
    packager = event["Packager"]
    main([batch, packager])
