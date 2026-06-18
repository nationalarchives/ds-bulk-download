import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


temp_existing_manifests = {
    "merlin_manifest.json": [
        {
            "name": "2025",
            "size": 128,
            "file_count": 1,
            "year": 2025,
            "month": None,
            "week": None,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2025-11",
            "size": 128,
            "file_count": 1,
            "year": 2025,
            "month": 11,
            "week": None,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2026-02",
            "size": 128,
            "file_count": 1,
            "year": 2026,
            "month": 2,
            "week": None,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2026-04",
            "size": 128,
            "file_count": 1,
            "year": 2026,
            "month": 4,
            "week": None,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2026-05-w1",
            "size": 128,
            "file_count": 1,
            "year": 2026,
            "month": 5,
            "week": 1,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2026-05-w2",
            "size": 128,
            "file_count": 1,
            "year": 2026,
            "month": 5,
            "week": 2,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2026-05-w3",
            "size": 128,
            "file_count": 1,
            "year": 2026,
            "month": 5,
            "week": 3,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2026-05-w4",
            "size": 128,
            "file_count": 1,
            "year": 2026,
            "month": 5,
            "week": 4,
            "created_timestamp": "2025-01-01T00:00:00",
        },
        {
            "name": "2026-05",
            "size": 128,
            "file_count": 1,
            "year": 2026,
            "month": 5,
            "week": None,
            "created_timestamp": "2025-01-01T00:00:00",
        },
    ],
    "grenfell_manifest.json": [],
}


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
        logger.debug(
            f"Packager initialized with from_datetime: {self.from_datetime}, to_datetime: {self.to_datetime}"
        )

    def scan(self, locations=None):
        if locations is None:
            raise ValueError("Locations must be provided for scanning.")
        for location in locations:
            logger.debug(f"Scanning location: {location}")
        # TODO: Get all files in location using from_datetime and to_datetime
        self.files = [
            {"Key": "2025-01-01.txt", "LastModified": datetime(2025, 1, 1), "Size": 1},
            {"Key": "2025-09-01.txt", "LastModified": datetime(2025, 9, 1), "Size": 2},
            {"Key": "2026-01-01.txt", "LastModified": datetime(2026, 1, 1), "Size": 4},
            {"Key": "2026-01-02.txt", "LastModified": datetime(2026, 1, 2), "Size": 8},
            {
                "Key": "2026-01-14.txt",
                "LastModified": datetime(2026, 1, 14),
                "Size": 16,
            },
            {"Key": "2026-02-01.txt", "LastModified": datetime(2026, 2, 1), "Size": 32},
            {"Key": "2026-04-01.txt", "LastModified": datetime(2026, 4, 1), "Size": 64},
            {
                "Key": "2026-05-31.txt",
                "LastModified": datetime(2026, 5, 31),
                "Size": 128,
            },
            {
                "Key": "2026-06-01.txt",
                "LastModified": datetime(2026, 6, 1),
                "Size": 256,
            },
            {
                "Key": "2026-06-02.txt",
                "LastModified": datetime(2026, 6, 2),
                "Size": 512,
            },
            {
                "Key": "2026-06-03.txt",
                "LastModified": datetime(2026, 6, 3),
                "Size": 1024,
            },
            {
                "Key": "2026-06-04.txt",
                "LastModified": datetime(2026, 6, 4),
                "Size": 2048,
            },
            {
                "Key": "2026-06-05.txt",
                "LastModified": datetime(2026, 6, 5),
                "Size": 4096,
            },
            {
                "Key": "2026-06-06.txt",
                "LastModified": datetime(2026, 6, 6),
                "Size": 8192,
            },
            {
                "Key": "2026-06-07.txt",
                "LastModified": datetime(2026, 6, 7),
                "Size": 16384,
            },
            {
                "Key": "2026-06-08.txt",
                "LastModified": datetime(2026, 6, 8),
                "Size": 32768,
            },
            {
                "Key": "2026-06-09.txt",
                "LastModified": datetime(2026, 6, 9),
                "Size": 65536,
            },
            {
                "Key": "2026-06-10.txt",
                "LastModified": datetime(2026, 6, 10),
                "Size": 131072,
            },
            {
                "Key": "2026-06-11.txt",
                "LastModified": datetime(2026, 6, 11),
                "Size": 262144,
            },
            {
                "Key": "2026-06-12.txt",
                "LastModified": datetime(2026, 6, 12),
                "Size": 524288,
            },
            {
                "Key": "2026-06-13.txt",
                "LastModified": datetime(2026, 6, 13),
                "Size": 1048576,
            },
            {
                "Key": "2026-06-14.txt",
                "LastModified": datetime(2026, 6, 14),
                "Size": 2097152,
            },
            {
                "Key": "2026-06-15.txt",
                "LastModified": datetime(2026, 6, 15),
                "Size": 4194304,
            },
            {
                "Key": "2026-06-16.txt",
                "LastModified": datetime(2026, 6, 16),
                "Size": 8388608,
            },
            {
                "Key": "2026-06-17.txt",
                "LastModified": datetime(2026, 6, 17),
                "Size": 16777216,
            },
            {
                "Key": "2026-06-18.txt",
                "LastModified": datetime(2026, 6, 18),
                "Size": 33554432,
            },
        ]
        # Filter out files based on from_datetime and to_datetime if they are set
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
        # TODO: Fetch existing manifest
        if f"{manifest_name}.json" not in temp_existing_manifests:
            logger.warning(f"-- No existing manifest found for: {manifest_name}")
            return []
        existing_manifest = temp_existing_manifests.get(f"{manifest_name}.json")
        manifest_type = TypeAdapter(list[BatchManifestItem])
        return manifest_type.validate_python(existing_manifest)

    def process(self, manifest_name=None):
        if manifest_name is None:
            raise ValueError("Manifest name must be provided for processing.")
        self.manifest_name = manifest_name

        if not self.files:
            raise ValueError("No files to process. Try running scan() first.")

        existing_manifest = self._get_existing_manifest(manifest_name)

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
        # TODO: ZIP and upload to S3

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
        logger.debug(f"Save manifest: {self.manifest_name}")
        manifest_json = json.dumps(manifest_content, indent=4)
        logger.debug(manifest_json)
        with open(f"tasks/{self.manifest_name}.json", "w") as f:
            f.write(manifest_json)


class ThisWeekPackager(Packager):
    def __init__(self):
        today_datetime = datetime.now()
        from_datetime = (
            today_datetime - timedelta(days=today_datetime.weekday())
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        to_datetime = (
            today_datetime + timedelta(days=6 - today_datetime.weekday())
        ).replace(hour=23, minute=59, second=59, microsecond=999999)
        self.week_index = today_datetime.day // 7 + 1
        package_name = f"{today_datetime.strftime('%Y-%m')}-w{self.week_index}"
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
        today_datetime = datetime.now()
        if today_datetime.month == 1:
            return  # Skip processing for January as there is no last month in the same year
        last_month = today_datetime.replace(day=1) + timedelta(days=-1)
        from_datetime = datetime(last_month.year, last_month.month, 1, 0, 0, 0, 0)
        to_datetime = datetime(
            last_month.year,
            last_month.month,
            (today_datetime.replace(day=1) - timedelta(days=1)).day,
            23,
            59,
            59,
            999999,
        )
        package_name = last_month.strftime("%Y-%m")
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
        package_name = str(yesteryear)
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
        super().__init__(package_name="all")

    def _manifest_items_to_remove(self, existing_manifest):
        return existing_manifest


class ChunkedPackager(AllPackager):
    def __init__(self, *args, **kwargs):
        self.chunk_size = int(args[0]) if args else 10
        super().__init__(package_name="all")

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
    locations = []
    manifest_name = None

    def __init__(self, packager_class, extra_args=None):
        self.packager_class = packager_class
        self.extra_args = extra_args or []

    def process(self):
        if not self.locations:
            raise ValueError("No locations have been defined for this batch.")
        if not self.manifest_name:
            raise ValueError("No manifest_name has been defined for this batch.")
        packager = self.packager_class(*self.extra_args)
        packager.scan(self.locations)
        packager.process(manifest_name=self.manifest_name)


class MerlinBatch(Batch):
    locations = [
        "/path/to/location1",
        "/path/to/location2",
    ]
    manifest_name = "merlin_manifest"


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
