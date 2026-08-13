"""CLI behaviour.

The CLI is a thin shell over the library, so these test the shell: argument handling,
file layout, and that the determinism contract survives the command line.
"""

from __future__ import annotations

import json

import pytest

from pkg.cli import main
from pkg.profiles.library import PROFILES


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
