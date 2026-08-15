"""CLI behaviour.

The CLI is a thin shell over the library, so these test the shell: argument handling,
file layout, and that the determinism contract survives the command line.
"""

from __future__ import annotations

import contextlib
import io
import json

import pytest

from carebundle import cli
from carebundle.cli import main
from carebundle.profiles.library import PROFILES


def test_profiles_lists_every_available_profile(capsys):
    assert main(["profiles"]) == 0
    output = capsys.readouterr().out
    for key in PROFILES:
        assert key in output
    assert "mixed" in output, "cohort mode should be discoverable from the CLI"


def test_mixed_cohort_from_the_cli(tmp_path, capsys):
    assert main(["generate", "--profile", "mixed", "--count", "6",
                 "--seed", "11", "--out", str(tmp_path)]) == 0
    capsys.readouterr()
    written = sorted(p.name for p in tmp_path.glob("*.json"))
    assert len(written) == 6
    assert all(name.startswith("mixed-11-") for name in written)


def test_a_closed_pipe_exits_cleanly_rather_than_tracebacking(monkeypatch):
    """`carebundle generate | head` is ordinary usage and must not look like a crash."""
    def explode(*_args, **_kwargs):
        raise BrokenPipeError

    monkeypatch.setitem(cli.COMMANDS, "profiles", explode)
    # dup2 must be stubbed: under pytest's default fd-level capture `sys.stdout` has a
    # real descriptor, so a live call would point pytest's own capture file at devnull
    # and silently break every test that runs afterwards.
    redirected: list[int] = []
    monkeypatch.setattr(cli.os, "dup2", lambda source, target: redirected.append(target))

    assert main(["profiles"]) == cli.EXIT_SIGPIPE
    assert redirected, "stdout was not redirected, so the shutdown flush will still raise"


def test_console_entry_point_restores_default_sigpipe(monkeypatch):
    """pyproject points the `carebundle` script at `run`, not `main` — keep it honest."""
    import signal

    called: list[tuple] = []
    monkeypatch.setattr(signal, "signal", lambda *a: called.append(a))
    monkeypatch.setattr(cli, "main", lambda: cli.EXIT_OK)

    assert cli.run() == cli.EXIT_OK
    if hasattr(signal, "SIGPIPE"):
        assert (signal.SIGPIPE, signal.SIG_DFL) in called


def test_restoring_sigpipe_off_the_main_thread_does_not_raise():
    """signal.signal raises off-thread; the handler is best-effort, never fatal."""
    import threading

    errors: list[BaseException] = []

    def target() -> None:
        try:
            cli._restore_default_sigpipe()
        except BaseException as exc:  # noqa: BLE001 - the point is that nothing escapes
            errors.append(exc)

    thread = threading.Thread(target=target)
    thread.start()
    thread.join()
    assert not errors


def test_silencing_stdout_survives_a_stream_with_no_file_descriptor():
    """Raising out of the broken-pipe handler would replace one crash with another."""
    class NoFileno(io.StringIO):
        def fileno(self):
            raise io.UnsupportedOperation("fileno")

    with contextlib.redirect_stdout(NoFileno()):
        cli._silence_stdout()  # must not raise


def test_ctrl_c_reports_interruption_rather_than_a_traceback(monkeypatch, capsys):
    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setitem(cli.COMMANDS, "profiles", interrupt)
    assert main(["profiles"]) == cli.EXIT_SIGINT
    assert "interrupted" in capsys.readouterr().err


def test_generate_writes_valid_json_to_stdout(capsys):
    assert main(["generate", "--profile", "healthy", "--seed", "1"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["resourceType"] == "Bundle"
    assert payload["type"] == "transaction"


def test_generate_writes_one_file_per_patient(tmp_path, capsys):
    main(["generate", "--count", "3", "--seed", "7", "--out", str(tmp_path)])
    capsys.readouterr()
    files = sorted(p.name for p in tmp_path.glob("*.json"))
    assert files == [
        "type2_diabetes-7-0000.json",
        "type2_diabetes-7-0001.json",
        "type2_diabetes-7-0002.json",
    ]


def test_generated_patients_differ_from_each_other(tmp_path, capsys):
    main(["generate", "--count", "3", "--seed", "7", "--out", str(tmp_path)])
    capsys.readouterr()
    contents = {p.read_text() for p in tmp_path.glob("*.json")}
    assert len(contents) == 3, "each patient in a run must be distinct"


def test_same_seed_produces_identical_cli_output(capsys):
    main(["generate", "--profile", "ckd_stage3", "--seed", "5"])
    first = capsys.readouterr().out
    main(["generate", "--profile", "ckd_stage3", "--seed", "5"])
    assert capsys.readouterr().out == first


def test_mixed_sex_alternates(tmp_path, capsys):
    main(["generate", "--count", "4", "--sex", "mixed", "--out", str(tmp_path)])
    capsys.readouterr()
    genders = []
    for path in sorted(tmp_path.glob("*.json")):
        payload = json.loads(path.read_text())
        patient = next(
            e["resource"] for e in payload["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        genders.append(patient["gender"])
    assert genders == ["female", "male", "female", "male"]


def test_reference_date_is_honoured_not_read_from_the_clock(capsys):
    main(["generate", "--profile", "healthy", "--reference-date", "2019-03-04"])
    payload = json.loads(capsys.readouterr().out)
    encounter = next(
        e["resource"] for e in payload["entry"]
        if e["resource"]["resourceType"] == "Encounter"
    )
    assert encounter["period"]["start"].startswith("2019-03-04")


@pytest.mark.parametrize(
    "argv,message",
    [
        (["generate", "--age-range", "70-40"], "exceeds high"),
        (["generate", "--age-range", "nonsense"], "must look like"),
    ],
)
def test_invalid_age_range_is_rejected(argv, message):
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert message in str(excinfo.value)


@pytest.mark.parametrize("argv", [["generate", "--count", "0"], ["generate", "--profile", "nope"]])
def test_invalid_arguments_exit_with_usage_error(argv):
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code == 2


def test_output_directory_is_created_if_absent(tmp_path, capsys):
    target = tmp_path / "nested" / "fixtures"
    main(["generate", "--out", str(target)])
    capsys.readouterr()
    assert list(target.glob("*.json"))
