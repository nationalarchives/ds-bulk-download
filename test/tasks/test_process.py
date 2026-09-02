import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("S3_EXPORT_BUCKET", "export-bucket")
os.environ.setdefault("S3_SOURCE_BUCKET_MERLIN", "source-bucket")
os.environ.setdefault("S3_SOURCE_PREFIX_MERLIN", "merlin")
os.environ.setdefault("S3_MANIFEST_NAME", "manifest.json")
os.environ.setdefault("S3_EXPORT_PREFIX_MERLIN", "merlin")

from tasks import process


class NoSuchKeyError(Exception):
    pass


class FakeS3Client:
    """A minimal in-memory stand-in for a boto3 S3 client."""

    def __init__(self, files=None, manifest_key=None, manifest_body=None):
        self.files = files or []
        self.manifest_key = manifest_key
        self.manifest_body = manifest_body
        self.put_object_calls = []
        self.upload_fileobj_calls = []
        self.exceptions = SimpleNamespace(NoSuchKey=NoSuchKeyError)

    def list_objects_v2(self, Bucket, Prefix=None, MaxKeys=1000, **kwargs):
        return {"Contents": self.files, "IsTruncated": False}

    def get_object(self, Bucket, Key):
        if Key == self.manifest_key:
            if self.manifest_body is None:
                raise self.exceptions.NoSuchKey()
            body = mock.MagicMock()
            body.read.return_value = json.dumps(self.manifest_body).encode("utf-8")
            return {"Body": body}
        body = mock.MagicMock()
        body.read.return_value = b"file-content"
        return {"Body": body}

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.put_object_calls.append({"Bucket": Bucket, "Key": Key, "Body": Body})
        if Key == self.manifest_key:
            self.manifest_body = json.loads(Body)

    def upload_fileobj(self, Fileobj, Bucket, Key, Config=None):
        while Fileobj.read(65536):
            pass
        self.upload_fileobj_calls.append({"Bucket": Bucket, "Key": Key})


class _FrozenDatetime(datetime):
    _frozen = None

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls._frozen.astimezone(tz)
        return cls._frozen


@contextmanager
def frozen_time(fixed_dt):
    frozen_cls = type("_FrozenDatetime", (_FrozenDatetime,), {"_frozen": fixed_dt})
    with mock.patch("tasks.process.datetime", frozen_cls):
        yield


def make_file(key, last_modified, size=10):
    return {"Key": key, "LastModified": last_modified, "Size": size}


SOURCE_BUCKET = "source-bucket"
SOURCE_PREFIX = "merlin"
EXPORT_BUCKET = "export-bucket"
EXPORT_PREFIX = "merlin"
MANIFEST_NAME = "manifest.json"
MANIFEST_KEY = f"{EXPORT_PREFIX}/{MANIFEST_NAME}"

# A "today" of 2026-09-02 (Wednesday) means:
#  - this month is September 2026
#  - this week is Mon 2026-08-31 -> Sun 2026-09-06 (crosses a month boundary)
#  - last month is August 2026
TODAY = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

SAMPLE_FILES = [
    make_file("2023/file.mp4", datetime(2023, 5, 10, tzinfo=timezone.utc)),
    make_file("2025/file.mp4", datetime(2025, 7, 20, tzinfo=timezone.utc)),
    make_file("2026-01/file.mp4", datetime(2026, 1, 10, tzinfo=timezone.utc)),
    make_file("2026-03/file.mp4", datetime(2026, 3, 5, tzinfo=timezone.utc)),
    make_file("2026-08-w1/file.mp4", datetime(2026, 8, 5, tzinfo=timezone.utc)),
    make_file("2026-08-w3/file.mp4", datetime(2026, 8, 20, tzinfo=timezone.utc)),
    make_file("2026-09-w1/file.mp4", datetime(2026, 9, 1, tzinfo=timezone.utc)),
    make_file("2026-09-w3/file.mp4", datetime(2026, 9, 15, tzinfo=timezone.utc)),
]


def run_packager(packager_class, extra_args=None, files=None, manifest_body=None):
    """Instantiate, scan and process a packager against a fake S3 client."""
    client = FakeS3Client(
        files=files if files is not None else SAMPLE_FILES,
        manifest_key=MANIFEST_KEY,
        manifest_body=manifest_body,
    )
    packager = packager_class(*(extra_args or []))
    packager.s3_client = client
    packager.scan(source=(SOURCE_BUCKET, SOURCE_PREFIX))
    packager.process(manifest_name=MANIFEST_NAME, export_prefix=EXPORT_PREFIX)
    return packager, client


class PackagerManifestTestCase(unittest.TestCase):
    """Covers every packager option and checks the manifest it writes."""

    def test_this_week_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.ThisWeekPackager)
        self.assertEqual(len(client.upload_fileobj_calls), 1)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], 1)

    def test_this_month_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.ThisMonthPackager)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        # Both September files fall inside "this month".
        self.assertEqual(items[0]["file_count"], 2)

    def test_this_year_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.ThisYearPackager)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        # Jan, Mar, Aug (x2) and Sep (x2) files all fall inside 2026.
        self.assertEqual(items[0]["file_count"], 6)

    def test_last_month_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.LastMonthPackager)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], 2)

    def test_last_year_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.LastYearPackager)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], 1)

    def test_all_weeks_this_month_packager_manifest(self):
        # AllWeeksThisMonthPackager only considers weeks whose Monday has
        # already occurred this month, so freeze "today" late in the month.
        week_files = [
            make_file(
                "2026-09-w2/file.mp4", datetime(2026, 9, 15, tzinfo=timezone.utc)
            ),
            make_file(
                "2026-09-w3/file.mp4", datetime(2026, 9, 22, tzinfo=timezone.utc)
            ),
        ]
        with frozen_time(datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)):
            _packager, client = run_packager(
                process.AllWeeksThisMonthPackager, files=week_files
            )
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(sum(item["file_count"] for item in items), 2)

    def test_all_months_this_year_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.AllMonthsThisYearPackager)
        items = client.manifest_body["items"]
        # January, March and August (current month is excluded).
        self.assertEqual(len(items), 3)
        self.assertEqual(sum(item["file_count"] for item in items), 4)

    def test_all_previous_years_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.AllPreviousYearsPackager)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(sum(item["file_count"] for item in items), 2)

    def test_all_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.AllPackager)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], len(SAMPLE_FILES))

    def test_chunked_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.ChunkedPackager, extra_args=["3"])
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual(sum(item["file_count"] for item in items), len(SAMPLE_FILES))

    def test_sized_packager_manifest(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.SizedPackager, extra_args=["20"])
        items = client.manifest_body["items"]
        self.assertEqual(sum(item["file_count"] for item in items), len(SAMPLE_FILES))
        self.assertTrue(all(item["total_size"] <= 20 for item in items[:-1]))


class ThisWeekPackagerMonthBoundaryTestCase(unittest.TestCase):
    """ThisWeekPackager must never package files spanning two months."""

    def test_never_crosses_a_month_boundary(self):
        boundary_dates = [
            datetime(2026, 9, 2, tzinfo=timezone.utc),  # week crosses Aug/Sep
            datetime(2026, 3, 1, tzinfo=timezone.utc),  # week crosses Feb/Mar
            datetime(
                2027, 1, 1, tzinfo=timezone.utc
            ),  # week crosses Dec/Jan (year change)
            datetime(2026, 6, 15, tzinfo=timezone.utc),  # mid-month, no boundary
        ]
        for fixed_now in boundary_dates:
            with self.subTest(today=fixed_now):
                with frozen_time(fixed_now):
                    packager = process.ThisWeekPackager()
                self.assertEqual(
                    packager.from_datetime.month, packager.to_datetime.month
                )
                self.assertEqual(packager.from_datetime.year, packager.to_datetime.year)
                # The range must still stay within the current month.
                self.assertEqual(packager.from_datetime.month, fixed_now.month)
                self.assertLessEqual(packager.from_datetime, fixed_now)
                self.assertGreaterEqual(packager.to_datetime, fixed_now)


class AllWeeksThisMonthPackagerMatchesThisWeekPackagerTestCase(unittest.TestCase):
    """AllWeeksThisMonthPackager must produce the same current-week chunk
    that ThisWeekPackager would, even early in the month before the
    month's first Monday has occurred."""

    def test_opening_partial_week_matches_this_week_packager(self):
        fixed_now = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
        files = [
            make_file("2026-09-01/file.mp4", datetime(2026, 9, 1, tzinfo=timezone.utc))
        ]
        with frozen_time(fixed_now):
            this_week_packager = process.ThisWeekPackager()
            _packager, client = run_packager(
                process.AllWeeksThisMonthPackager, files=files
            )
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        from_datetime = datetime.fromisoformat(items[0]["from_datetime"])
        to_datetime = datetime.fromisoformat(items[0]["to_datetime"])
        self.assertEqual(from_datetime, this_week_packager.from_datetime)
        self.assertEqual(to_datetime, this_week_packager.to_datetime)
        self.assertEqual(items[0]["file_count"], 1)


class AllWeeksThisMonthPackagerMonthBoundaryTestCase(unittest.TestCase):
    """Each week chunk must never spill over into the following month."""

    def test_last_week_of_month_never_crosses_a_month_boundary(self):
        # 2026-09-28 is a Monday, but September only has 30 days, so the
        # Mon-Sun week for that Monday would otherwise run into October.
        fixed_now = datetime(2026, 9, 30, 12, 0, 0, tzinfo=timezone.utc)
        overflowing_week_file = [
            make_file("2026-09-w5/file.mp4", datetime(2026, 9, 29, tzinfo=timezone.utc))
        ]
        with frozen_time(fixed_now):
            _packager, client = run_packager(
                process.AllWeeksThisMonthPackager, files=overflowing_week_file
            )
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        from_datetime = datetime.fromisoformat(items[0]["from_datetime"])
        to_datetime = datetime.fromisoformat(items[0]["to_datetime"])
        self.assertEqual(from_datetime.month, to_datetime.month)
        self.assertEqual(to_datetime.month, 9)
        self.assertEqual(items[0]["file_count"], 1)


class AllWeeksThisMonthPackagerRerunTestCase(unittest.TestCase):
    """Regression test: weeks with no new chunk must not be wiped without one."""

    def test_early_in_the_month_keeps_previously_recorded_weeks(self):
        # Running on day 2 of the month means week two's Monday (Sep 7)
        # hasn't occurred yet, so no replacement chunk is generated for it.
        # That existing weekly entry must survive this run, not vanish, even
        # though a new chunk is generated for the opening partial week.
        existing_manifest = {
            "packager": "all_weeks_this_month",
            "packager_group": "by_date",
            "items": [
                {
                    "name": "07 to 13 September 2026",
                    "file": f"{EXPORT_PREFIX}/2026-09-w1.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-09-13T00:00:00Z",
                    "from_datetime": "2026-09-07T00:00:00Z",
                    "to_datetime": "2026-09-13T23:59:59.999999Z",
                }
            ],
        }
        files = [
            make_file("2026-09-01/file.mp4", datetime(2026, 9, 1, tzinfo=timezone.utc))
        ]
        with frozen_time(datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)):
            _packager, client = run_packager(
                process.AllWeeksThisMonthPackager,
                files=files,
                manifest_body=existing_manifest,
            )
        item_names = [item["name"] for item in client.manifest_body["items"]]
        self.assertIn("07 to 13 September 2026", item_names)
        self.assertIn("1 to 6 September 2026", item_names)

    def test_replaces_only_the_week_it_regenerates(self):
        existing_manifest = {
            "packager": "all_weeks_this_month",
            "packager_group": "by_date",
            "items": [
                {
                    "name": "07 to 13 September 2026",
                    "file": f"{EXPORT_PREFIX}/2026-09-w1.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-09-13T00:00:00Z",
                    "from_datetime": "2026-09-07T00:00:00Z",
                    "to_datetime": "2026-09-13T23:59:59.999999Z",
                },
                {
                    "name": "14 to 20 September 2026",
                    "file": f"{EXPORT_PREFIX}/2026-09-w2.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-09-20T00:00:00Z",
                    "from_datetime": "2026-09-14T00:00:00Z",
                    "to_datetime": "2026-09-20T23:59:59.999999Z",
                },
            ],
        }
        # Only week 2 (Sep 14-20) has a file this run.
        files = [
            make_file("2026-09-15/file.mp4", datetime(2026, 9, 15, tzinfo=timezone.utc))
        ]
        with frozen_time(datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)):
            _packager, client = run_packager(
                process.AllWeeksThisMonthPackager,
                files=files,
                manifest_body=existing_manifest,
            )
        items = client.manifest_body["items"]
        item_names = [item["name"] for item in items]
        self.assertIn("07 to 13 September 2026", item_names)
        self.assertEqual(item_names.count("14 to 20 September 2026"), 1)


class ThisMonthPackagerMonthBoundaryTestCase(unittest.TestCase):
    """ThisMonthPackager's range must never span two different months."""

    def test_never_crosses_a_month_boundary(self):
        boundary_dates = [
            datetime(2026, 9, 30, tzinfo=timezone.utc),  # last day of the month
            datetime(2026, 2, 1, tzinfo=timezone.utc),  # first day of the month
        ]
        for fixed_now in boundary_dates:
            with self.subTest(today=fixed_now):
                with frozen_time(fixed_now):
                    packager = process.ThisMonthPackager()
                self.assertEqual(
                    packager.from_datetime.month, packager.to_datetime.month
                )
                self.assertEqual(packager.from_datetime.month, fixed_now.month)


class AllMonthsThisYearPackagerMonthBoundaryTestCase(unittest.TestCase):
    """Each month chunk must never span two different months."""

    def test_month_chunks_never_cross_a_month_boundary(self):
        fixed_now = datetime(2026, 9, 2, tzinfo=timezone.utc)
        files = [
            make_file("2026-01/file.mp4", datetime(2026, 1, 31, tzinfo=timezone.utc)),
            make_file("2026-02/file.mp4", datetime(2026, 2, 28, tzinfo=timezone.utc)),
        ]
        with frozen_time(fixed_now):
            _packager, client = run_packager(
                process.AllMonthsThisYearPackager, files=files
            )
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 2)
        for item in items:
            from_datetime = datetime.fromisoformat(item["from_datetime"])
            to_datetime = datetime.fromisoformat(item["to_datetime"])
            self.assertEqual(from_datetime.month, to_datetime.month)


class AllPackagerTestCase(unittest.TestCase):
    """AllPackager should bundle every file into a single manifest item."""

    def test_bundles_every_file_regardless_of_date(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.AllPackager)
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "All files")
        self.assertEqual(items[0]["file"], f"{EXPORT_PREFIX}/all.zip")
        self.assertEqual(items[0]["file_count"], len(SAMPLE_FILES))
        self.assertEqual(
            items[0]["total_size"], sum(file["Size"] for file in SAMPLE_FILES)
        )

    def test_rerun_replaces_the_previous_all_files_entry(self):
        existing_manifest = {
            "packager": "all",
            "packager_group": "all",
            "items": [
                {
                    "name": "All files",
                    "file": f"{EXPORT_PREFIX}/all.zip",
                    "total_size": 1,
                    "file_count": 1,
                    "created_timestamp": "2026-01-01T00:00:00Z",
                }
            ],
        }
        with frozen_time(TODAY):
            _packager, client = run_packager(
                process.AllPackager, manifest_body=existing_manifest
            )
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], len(SAMPLE_FILES))


class ChunkedPackagerTestCase(unittest.TestCase):
    """ChunkedPackager should split files into fixed-size batches."""

    def test_default_chunk_size(self):
        with frozen_time(TODAY):
            packager, client = run_packager(process.ChunkedPackager)
        self.assertEqual(packager.chunk_size, 1000)
        items = client.manifest_body["items"]
        # All files fit in a single default-sized (1000) batch.
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], len(SAMPLE_FILES))

    def test_custom_chunk_size_splits_files_evenly(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(process.ChunkedPackager, extra_args=["3"])
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual([item["file_count"] for item in items], [3, 3, 2])
        self.assertEqual(items[0]["name"], "Batch 1 of 3")
        self.assertEqual(items[0]["file"], f"{EXPORT_PREFIX}/all_0001.zip")

    def test_chunk_size_larger_than_file_count_creates_one_batch(self):
        with frozen_time(TODAY):
            _packager, client = run_packager(
                process.ChunkedPackager, extra_args=["100"]
            )
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], len(SAMPLE_FILES))


class SizedPackagerTestCase(unittest.TestCase):
    """SizedPackager should split files into batches bounded by total size."""

    def test_default_chunk_size(self):
        with frozen_time(TODAY):
            packager, client = run_packager(process.SizedPackager)
        self.assertEqual(packager.chunk_size, 100000)
        items = client.manifest_body["items"]
        # All files easily fit within the default 100000 byte budget.
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["file_count"], len(SAMPLE_FILES))

    def test_custom_chunk_size_groups_by_total_size(self):
        # Each SAMPLE_FILES entry is 10 bytes, so a budget of 25 bytes fits
        # two files per batch before rolling over into a new one.
        with frozen_time(TODAY):
            _packager, client = run_packager(process.SizedPackager, extra_args=["25"])
        items = client.manifest_body["items"]
        self.assertEqual(sum(item["file_count"] for item in items), len(SAMPLE_FILES))
        self.assertTrue(all(item["total_size"] <= 25 for item in items))
        self.assertTrue(all(item["file_count"] <= 2 for item in items))

    def test_a_single_oversized_file_still_gets_its_own_batch(self):
        oversized_files = [
            make_file("small.mp4", datetime(2026, 1, 1, tzinfo=timezone.utc), size=10),
            make_file("huge.mp4", datetime(2026, 1, 2, tzinfo=timezone.utc), size=1000),
            make_file("small2.mp4", datetime(2026, 1, 3, tzinfo=timezone.utc), size=10),
        ]
        with frozen_time(TODAY):
            _packager, client = run_packager(
                process.SizedPackager, extra_args=["20"], files=oversized_files
            )
        items = client.manifest_body["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual([item["file_count"] for item in items], [1, 1, 1])
        self.assertEqual([item["total_size"] for item in items], [10, 1000, 10])


class ThisYearPackagerTestCase(unittest.TestCase):
    """ThisYearPackager should bundle only files from the current year."""

    def test_never_crosses_a_year_boundary(self):
        with frozen_time(TODAY):
            packager = process.ThisYearPackager()
        self.assertEqual(packager.from_datetime.year, packager.to_datetime.year)
        self.assertEqual(packager.from_datetime.year, TODAY.year)
        self.assertEqual(packager.from_datetime.month, 1)
        self.assertEqual(packager.to_datetime.month, 12)

    def test_only_replaces_entries_fully_within_this_year(self):
        existing_manifest = {
            "packager": "this_year",
            "packager_group": "by_date",
            "items": [
                {
                    "name": "2026",
                    "file": f"{EXPORT_PREFIX}/2026.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-06-01T00:00:00Z",
                    "from_datetime": "2026-01-01T00:00:00Z",
                    "to_datetime": "2026-12-31T23:59:59.999999Z",
                },
                {
                    "name": "2025",
                    "file": f"{EXPORT_PREFIX}/2025.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2025-12-31T00:00:00Z",
                    "from_datetime": "2025-01-01T00:00:00Z",
                    "to_datetime": "2025-12-31T23:59:59.999999Z",
                },
            ],
        }
        with frozen_time(TODAY):
            _packager, client = run_packager(
                process.ThisYearPackager, manifest_body=existing_manifest
            )
        item_names = [item["name"] for item in client.manifest_body["items"]]
        self.assertIn("2025", item_names)
        self.assertEqual(item_names.count("2026"), 1)


class LastYearPackagerTestCase(unittest.TestCase):
    """LastYearPackager should bundle only files from the previous year."""

    def test_never_crosses_a_year_boundary(self):
        with frozen_time(TODAY):
            packager = process.LastYearPackager()
        self.assertEqual(packager.from_datetime.year, packager.to_datetime.year)
        self.assertEqual(packager.from_datetime.year, TODAY.year - 1)
        self.assertEqual(packager.from_datetime.month, 1)
        self.assertEqual(packager.to_datetime.month, 12)

    def test_removes_all_entries_for_the_previous_year(self):
        existing_manifest = {
            "packager": "all_months_this_year",
            "packager_group": "by_date",
            "items": [
                {
                    "name": "March 2025",
                    "file": f"{EXPORT_PREFIX}/2025-03.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2025-03-31T00:00:00Z",
                    "from_datetime": "2025-03-01T00:00:00Z",
                    "to_datetime": "2025-03-31T23:59:59.999999Z",
                },
                {
                    "name": "2024",
                    "file": f"{EXPORT_PREFIX}/2024.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2024-12-31T00:00:00Z",
                    "from_datetime": "2024-01-01T00:00:00Z",
                    "to_datetime": "2024-12-31T23:59:59.999999Z",
                },
            ],
        }
        with frozen_time(TODAY):
            packager, client = run_packager(
                process.LastYearPackager, manifest_body=existing_manifest
            )
        item_names = [item["name"] for item in client.manifest_body["items"]]
        self.assertNotIn("March 2025", item_names)
        self.assertIn("2024", item_names)
        self.assertIn(packager.name, item_names)


class AllPreviousYearsPackagerTestCase(unittest.TestCase):
    """AllPreviousYearsPackager should chunk by year, excluding this year."""

    def test_excludes_the_current_year_and_orders_newest_first(self):
        files = [
            make_file("2022/file.mp4", datetime(2022, 6, 1, tzinfo=timezone.utc)),
            make_file("2023/file.mp4", datetime(2023, 6, 1, tzinfo=timezone.utc)),
            make_file("2024/file.mp4", datetime(2024, 6, 1, tzinfo=timezone.utc)),
            make_file(
                "2026-current/file.mp4", datetime(2026, 6, 1, tzinfo=timezone.utc)
            ),
        ]
        with frozen_time(TODAY):
            _packager, client = run_packager(
                process.AllPreviousYearsPackager, files=files
            )
        items = client.manifest_body["items"]
        self.assertEqual([item["name"] for item in items], ["2024", "2023", "2022"])
        self.assertEqual(sum(item["file_count"] for item in items), 3)

    def test_replaces_years_it_regenerates_and_keeps_the_rest(self):
        existing_manifest = {
            "packager": "all_previous_years",
            "packager_group": "by_date",
            "items": [
                {
                    "name": "2024",
                    "file": f"{EXPORT_PREFIX}/2024.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2024-12-31T00:00:00Z",
                    "from_datetime": "2024-01-01T00:00:00Z",
                    "to_datetime": "2024-12-31T23:59:59.999999Z",
                },
                {
                    "name": "2026",
                    "file": f"{EXPORT_PREFIX}/2026.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-06-01T00:00:00Z",
                    "from_datetime": "2026-01-01T00:00:00Z",
                    "to_datetime": "2026-12-31T23:59:59.999999Z",
                },
            ],
        }
        # Only 2024 has files this run, so only the stale "2024" entry
        # should be replaced; "2026" is out of range and always kept.
        files = [make_file("2024/file.mp4", datetime(2024, 6, 1, tzinfo=timezone.utc))]
        with frozen_time(TODAY):
            _packager, client = run_packager(
                process.AllPreviousYearsPackager,
                files=files,
                manifest_body=existing_manifest,
            )
        items = client.manifest_body["items"]
        item_names = [item["name"] for item in items]
        self.assertEqual(item_names.count("2024"), 1)
        self.assertIn("2026", item_names)

    def test_does_not_remove_a_year_with_no_replacement_chunk(self):
        # Regression test: a stale entry must not be wiped just because it
        # falls within the packager's date range if no fresh chunk was
        # generated to replace it this run (e.g. no files scanned for it).
        existing_manifest = {
            "packager": "all_previous_years",
            "packager_group": "by_date",
            "items": [
                {
                    "name": "2024",
                    "file": f"{EXPORT_PREFIX}/2024.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2024-12-31T00:00:00Z",
                    "from_datetime": "2024-01-01T00:00:00Z",
                    "to_datetime": "2024-12-31T23:59:59.999999Z",
                },
            ],
        }
        files = [make_file("2023/file.mp4", datetime(2023, 6, 1, tzinfo=timezone.utc))]
        with frozen_time(TODAY):
            _packager, client = run_packager(
                process.AllPreviousYearsPackager,
                files=files,
                manifest_body=existing_manifest,
            )
        item_names = [item["name"] for item in client.manifest_body["items"]]
        self.assertIn("2024", item_names)
        self.assertIn("2023", item_names)
        self.assertIn("2023", item_names)


class LastMonthPackagerRemovesWeeklyEntriesTestCase(unittest.TestCase):
    """LastMonthPackager must clear out all of last month's weekly manifest entries."""

    def test_removes_all_weekly_entries_for_previous_month(self):
        existing_manifest = {
            "packager": "all_weeks_this_month",
            "packager_group": "by_date",
            "items": [
                {
                    "name": "August 2026 (week 1)",
                    "file": f"{EXPORT_PREFIX}/2026-08-w1.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-08-05T00:00:00Z",
                    "from_datetime": "2026-08-03T00:00:00Z",
                    "to_datetime": "2026-08-09T23:59:59.999999Z",
                },
                {
                    "name": "August 2026 (week 3)",
                    "file": f"{EXPORT_PREFIX}/2026-08-w3.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-08-20T00:00:00Z",
                    "from_datetime": "2026-08-17T00:00:00Z",
                    "to_datetime": "2026-08-23T23:59:59.999999Z",
                },
                {
                    "name": "July 2026",
                    "file": f"{EXPORT_PREFIX}/2026-07.zip",
                    "total_size": 10,
                    "file_count": 1,
                    "created_timestamp": "2026-07-31T00:00:00Z",
                    "from_datetime": "2026-07-01T00:00:00Z",
                    "to_datetime": "2026-07-31T23:59:59.999999Z",
                },
            ],
        }
        with frozen_time(TODAY):
            packager, client = run_packager(
                process.LastMonthPackager, manifest_body=existing_manifest
            )
        item_names = [item["name"] for item in client.manifest_body["items"]]
        self.assertNotIn("August 2026 (week 1)", item_names)
        self.assertNotIn("August 2026 (week 3)", item_names)
        self.assertIn("July 2026", item_names)
        self.assertIn(packager.name, item_names)


if __name__ == "__main__":
    unittest.main()
