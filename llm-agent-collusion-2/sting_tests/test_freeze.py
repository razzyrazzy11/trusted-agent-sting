"""Protocol freeze: verifiable with standard tools, detects changes, never hashes its own record,
and every data folder records the protocol it was collected under."""
import hashlib
import shutil
import subprocess

import pytest

from sting import freeze


def _copy_protocol(tmp_path):
    root = tmp_path / "sting"
    for f in freeze.PROTOCOL_FILES:
        (root / f).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(freeze.ROOT / f, root / f)
    return root


def test_protocol_hash_is_verifiable_with_sha256sum(tmp_path):
    if not shutil.which("sha256sum"):
        pytest.skip("sha256sum not available")
    root = _copy_protocol(tmp_path)
    listing = subprocess.run(["sha256sum", *[f"sting/{f}" for f in freeze.PROTOCOL_FILES]], cwd=tmp_path,
                             capture_output=True, check=True).stdout
    assert hashlib.sha256(listing).hexdigest() == freeze.protocol_hash(freeze.file_hashes(root))


def test_freeze_check_and_change_detection(tmp_path, capsys):
    root = _copy_protocol(tmp_path)
    before = freeze.protocol_hash(freeze.file_hashes(root))
    assert freeze.check(root) == 1                                   # not frozen yet
    assert freeze.write_freeze(root) == 0
    assert freeze.status(root)["protocol_hash"] == before            # recording the hash does not change it
    assert freeze.check(root) == 0
    (root / "config.py").write_text((root / "config.py").read_text() + "\n# post-freeze edit\n")
    st = freeze.status(root)
    assert not st["match"] and st["changed"] == ["sting/config.py"]
    assert freeze.check(root) == 1
    assert freeze.write_freeze(root) == 1                            # no silent re-freeze
    assert freeze.write_freeze(root, force=True) == 0 and freeze.check(root) == 0


def test_runs_record_the_protocol_hash(tmp_path, quiet):
    from sting.analysis.load import load
    from sting.config import PRIMARY_MODEL, SequenceConfig
    from sting.sequence import run_sequence
    from sting.stub import stub_factory
    cfg = SequenceConfig(arm="B1", seed=0, model=PRIMARY_MODEL, n_games=1, offer_game=1, probes=False)
    with quiet():
        meta = run_sequence(cfg, tmp_path / "live", stub_factory=stub_factory(0))
    assert meta["protocol"]["protocol_hash"] == freeze.status()["protocol_hash"]
    data = load(tmp_path)
    assert [p["protocol_hash"] for p in data.protocol] == [meta["protocol"]["protocol_hash"]]
    assert data.seqs["protocol_hash"].tolist() == [meta["protocol"]["protocol_hash"]]
