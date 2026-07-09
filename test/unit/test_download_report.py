"""Tests for the DownloadReport returned by download_from_yaml and main."""

# ruff: noqa: D103

from unittest import mock

import pytest
import typer

from kghub_downloader.download_utils import download_from_yaml
from kghub_downloader.main import main
from kghub_downloader.model import DownloadOptions, DownloadReport


def fake_download(item, outfile_path, options):
    outfile_path.write_text("downloaded")


def failing_download(item, outfile_path, options):
    raise RuntimeError("boom")


def write_yaml(tmp_path, resources):
    yaml_file = tmp_path / "download.yaml"
    yaml_file.write_text("\n".join(f"- url: {url}\n  local_name: {name}" for url, name in resources))
    return str(yaml_file)


def test_report_downloaded_and_skipped(tmp_path):
    yaml_file = write_yaml(
        tmp_path,
        [
            ("http://example.com/a.txt", "a.txt"),
            ("http://example.com/b.txt", "b.txt"),
        ],
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    # b.txt already exists, so it should be served from cache
    (output_dir / "b.txt").write_text("cached")

    with mock.patch.dict("kghub_downloader.schemes.available_schemes", {"http": fake_download}):
        report = download_from_yaml(yaml_file, str(output_dir))

    assert isinstance(report, DownloadReport)
    assert report.downloaded == [(output_dir / "a.txt").resolve()]
    assert report.skipped == [(output_dir / "b.txt").resolve()]
    assert report.failed == []
    assert report.any_downloaded
    assert all(p.is_absolute() for p in report.downloaded + report.skipped)


def test_report_ignore_cache_counts_as_downloaded(tmp_path):
    yaml_file = write_yaml(tmp_path, [("http://example.com/a.txt", "a.txt")])
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "a.txt").write_text("cached")

    options = DownloadOptions(ignore_cache=True)
    with mock.patch.dict("kghub_downloader.schemes.available_schemes", {"http": fake_download}):
        report = download_from_yaml(yaml_file, str(output_dir), download_options=options)

    assert report.downloaded == [(output_dir / "a.txt").resolve()]
    assert report.skipped == []


def test_report_failed(tmp_path):
    yaml_file = write_yaml(tmp_path, [("http://example.com/a.txt", "a.txt")])
    output_dir = tmp_path / "output"

    options = DownloadOptions(fail_on_error=False)
    with mock.patch.dict("kghub_downloader.schemes.available_schemes", {"http": failing_download}):
        report = download_from_yaml(yaml_file, str(output_dir), download_options=options)

    assert report.downloaded == []
    assert report.failed == [(output_dir / "a.txt").resolve()]
    assert not report.any_downloaded


def test_report_fail_on_error_raises(tmp_path):
    yaml_file = write_yaml(tmp_path, [("http://example.com/a.txt", "a.txt")])
    output_dir = tmp_path / "output"

    options = DownloadOptions(fail_on_error=True)
    with mock.patch.dict("kghub_downloader.schemes.available_schemes", {"http": failing_download}):
        with pytest.raises(RuntimeError):
            download_from_yaml(yaml_file, str(output_dir), download_options=options)


def test_main_returns_report_when_called_directly(tmp_path):
    yaml_file = write_yaml(tmp_path, [("http://example.com/a.txt", "a.txt")])
    output_dir = tmp_path / "output"

    with mock.patch.dict("kghub_downloader.schemes.available_schemes", {"http": fake_download}):
        report = main(yaml_file=yaml_file, output_dir=str(output_dir))

    assert isinstance(report, DownloadReport)
    assert report.downloaded == [(output_dir / "a.txt").resolve()]


def test_main_exits_nonzero_on_failure(tmp_path):
    yaml_file = write_yaml(tmp_path, [("http://example.com/a.txt", "a.txt")])
    output_dir = tmp_path / "output"

    with mock.patch.dict("kghub_downloader.schemes.available_schemes", {"http": failing_download}):
        with pytest.raises(typer.Exit) as exc_info:
            main(yaml_file=yaml_file, output_dir=str(output_dir))

    assert exc_info.value.exit_code == 1
