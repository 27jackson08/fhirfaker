"""The NHANES fetch list, checked without touching the network.

`fetch.FILES` duplicates knowledge that lives in two other modules: which files the
calibration reads, and which the transfer analysis reads. Duplicated knowledge drifts —
add a variable to `nhanes.VARIABLES` from a file not on the fetch list and the download
is silently incomplete, which surfaces much later as a confusing parse error.

Nothing here makes a network request. The download path is exercised by actually running
it; these guard the parts that can go wrong quietly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from carebundle.calibration import fetch
from carebundle.calibration.nhanes import VARIABLES
from carebundle.fidelity.transfer import FILES as TRANSFER_FILES


def _required() -> set[str]:
    """Every NHANES file the offline tooling actually opens."""
    # P_DEMO is read directly by both loaders rather than via VARIABLES.
    return (set(VARIABLES) | {"P_DEMO"}) | set(TRANSFER_FILES)


def test_fetch_covers_everything_the_tooling_reads():
    missing = _required() - set(fetch.FILES)
    assert not missing, (
        f"these files are read by the tooling but would never be downloaded: "
        f"{sorted(missing)}"
    )


def test_fetch_downloads_nothing_it_does_not_need():
    """A superfluous file is a slower download and a claim nobody checks."""
    extra = set(fetch.FILES) - _required()
    assert not extra, f"fetch downloads files nothing reads: {sorted(extra)}"


def test_file_stems_carry_no_extension():
    """The stem is combined with '.xpt' by both the URL and the path builder."""
    for stem in fetch.FILES:
        assert not stem.endswith(".xpt"), f"{stem} would produce {stem}.xpt.xpt"
        assert stem.startswith("P_"), f"{stem} is not a pre-pandemic NHANES stem"


def test_the_download_url_is_the_public_data_files_endpoint():
    assert fetch.BASE_URL.startswith("https://"), "NHANES must not be fetched over http"
    assert "wwwn.cdc.gov" in fetch.BASE_URL


def test_existing_files_are_kept_rather_than_refetched(tmp_path: Path, monkeypatch):
    """Skipping what is present is what makes a failed run resumable."""
    def explode(*args, **kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("fetch attempted a download for a file already present")

    monkeypatch.setattr(fetch.urllib.request, "urlopen", explode)
    for stem in fetch.FILES:
        (tmp_path / f"{stem}.xpt").write_bytes(b"already here")

    written = fetch.fetch(tmp_path, force=False)
    assert len(written) == len(fetch.FILES)


def test_a_zero_byte_file_is_refetched_not_trusted(tmp_path: Path, monkeypatch):
    """A truncated download must not be mistaken for a complete one."""
    attempted: list[str] = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def read(self): return b"payload"

    def record(url, timeout=None):
        attempted.append(url)
        return Response()

    monkeypatch.setattr(fetch.urllib.request, "urlopen", record)
    (tmp_path / "P_DEMO.xpt").write_bytes(b"")           # truncated
    (tmp_path / "P_GHB.xpt").write_bytes(b"complete")    # fine

    fetch.fetch(tmp_path, force=False)
    assert any("P_DEMO" in url for url in attempted), "empty file was trusted"
    assert not any("P_GHB" in url for url in attempted), "complete file was refetched"


def test_one_failed_file_does_not_abort_the_rest(tmp_path: Path, monkeypatch):
    """A transient CDC failure should not mean restarting the whole download."""
    class Response:
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def read(self): return b"payload"

    def flaky(url, timeout=None):
        if "P_DEMO" in url:
            raise fetch.urllib.error.URLError("simulated outage")
        return Response()

    monkeypatch.setattr(fetch.urllib.request, "urlopen", flaky)
    written = fetch.fetch(tmp_path, force=False)

    assert len(written) == len(fetch.FILES) - 1
    assert not (tmp_path / "P_DEMO.xpt").exists()


@pytest.mark.parametrize("stem", fetch.FILES)
def test_every_file_is_documented_somewhere(stem):
    """A reader should be able to tell why each file is downloaded."""
    source = Path(fetch.__file__).read_text(encoding="utf-8")
    line = next(l for l in source.splitlines() if f'"{stem}"' in l)
    assert "#" in line, f"{stem} is listed with no comment saying what it is for"


def test_cli_reports_success_when_every_file_arrives(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(fetch, "fetch", lambda d, force=False: list(fetch.FILES))
    monkeypatch.setattr("sys.argv", ["fetch", "--data-dir", str(tmp_path)])

    assert fetch.main() == 0
    out = capsys.readouterr().out
    assert f"{len(fetch.FILES)}/{len(fetch.FILES)} files" in out
    assert "carebundle.calibration.nhanes" in out, "should point at what consumes them"


def test_cli_exits_nonzero_when_files_are_missing(tmp_path: Path, monkeypatch, capsys):
    """A partial download must not look like success to a script or a CI step."""
    monkeypatch.setattr(fetch, "fetch", lambda d, force=False: list(fetch.FILES[:-2]))
    monkeypatch.setattr("sys.argv", ["fetch", "--data-dir", str(tmp_path)])

    assert fetch.main() == 1
    assert "2 missing" in capsys.readouterr().out
