from breedcafs_migration import validate
from breedcafs_migration.validate import Validation


def test_same_reports_missing_and_unexpected():
    validation = Validation()
    validation.same("all there", {1, 2}, [2, 1])
    validation.same("one missing, one extra", {1, 2}, [2, 3])
    assert [check.passed for check in validation.checks] == [True, False]
    assert validation.checks[1].detail == "2 of 2; missing 1, e.g. [1]; unexpected 1, e.g. [3]"
    assert not validation.passed


def test_report(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, 'BREEDCAFS_DATA_DIR', tmp_path)
    validation = Validation()
    validation.all("Units have their subject", [], 3)
    validation.all("Units have their parents", ['1_T1'], 3)
    path = validate.write_report(validation)
    lines = path.read_text().splitlines()
    assert lines[0] == "# Migration validation: FAILED"
    assert "| Units have their subject | pass | 3 of 3 |" in lines
    assert "| Units have their parents | FAIL | 2 of 3; e.g. ['1_T1'] |" in lines
