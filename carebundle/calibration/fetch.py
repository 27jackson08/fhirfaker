"""Download the NHANES files the offline tooling needs.

The claims in this repository are meant to be checkable, and two of them —  the
calibration targets and the train-on-synthetic transfer result — need the NHANES
2017–March 2020 public files. Those are not vendored: they are large, they belong to
NCHS, and a copy in this repository would go stale silently.

What was missing was the step between "not vendored" and "check it yourself". Knowing
*which* eleven files, under which of several CDC URL layouts, is not something a reader
should have to reverse-engineer from a docstring.

    python -m carebundle.calibration.fetch --data-dir nhanes/

The files are public domain (NCHS), so redistribution is not the obstacle — staleness
and size are. Downloading them takes a couple of minutes.
"""

from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles"

# Every file the offline tooling reads. The union of what `nhanes.py` needs to derive
# marginals, correlations and prevalences, and what `fidelity/transfer.py` needs to
# assemble a real held-out test set.
FILES = (
    "P_DEMO",     # demographics: age, sex — the join key for everything else
    "P_GHB",      # glycohaemoglobin
    "P_DIQ",      # diabetes questionnaire: DIQ010, the diagnosis stratum
    "P_BPQ",      # blood pressure questionnaire: BPQ020, the comorbidity prevalence
    "P_BIOPRO",   # standard biochemistry profile
    "P_TCHOL",    # total cholesterol
    "P_HDL",      # HDL
    "P_TRIGLY",   # triglycerides and calculated LDL
    "P_BMX",      # body measurements
    "P_BPXO",     # oscillometric blood pressure
    "P_CBC",      # complete blood count
)


def fetch(data_dir: Path, *, force: bool = False) -> list[Path]:
    """Download every required file, skipping ones already present."""
    data_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for stem in FILES:
        target = data_dir / f"{stem}.xpt"
        if target.exists() and target.stat().st_size > 0 and not force:
            print(f"  have    {target.name} ({target.stat().st_size:,} bytes)")
            written.append(target)
            continue
        url = f"{BASE_URL}/{stem}.xpt"
        try:
            with urllib.request.urlopen(url, timeout=300) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as error:
            # Report and continue: a partial set still lets some tooling run, and one
            # transient CDC failure should not mean starting the whole download again.
            print(f"  FAILED  {stem}.xpt — {error}")
            continue
        target.write_bytes(payload)
        print(f"  fetched {target.name} ({len(payload):,} bytes)")
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="re-download existing files")
    args = parser.parse_args()

    written = fetch(args.data_dir, force=args.force)
    missing = len(FILES) - len(written)
    print()
    print(f"{len(written)}/{len(FILES)} files in {args.data_dir}")
    if missing:
        print(f"{missing} missing — rerun to retry, the rest are skipped as already present")
        return 1
    print("Next:")
    print(f"  python -m carebundle.calibration.nhanes --data-dir {args.data_dir}")
    print(f"  python -m carebundle.fidelity.transfer  --data-dir {args.data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
