import json

from exact_linter.cli import main


def test_update_baseline_writes_current_findings(tmp_path, capsys):
    (tmp_path / "p.py").write_text("R = 0.017453292519943295\n")
    baseline = tmp_path / "baseline.json"
    code = main(
        [str(tmp_path), "--baseline", str(baseline), "--update-baseline"],
    )
    assert code == 0
    assert baseline.exists()
    data = json.loads(baseline.read_text())
    assert data["version"] == 1
    assert len(data["entries"]) == 1
    assert data["entries"][0]["form"] == "pi/180"


def test_baselined_finding_is_suppressed(tmp_path, capsys):
    (tmp_path / "p.py").write_text("R = 0.017453292519943295\n")
    baseline = tmp_path / "baseline.json"
    main([str(tmp_path), "--baseline", str(baseline), "--update-baseline"])
    capsys.readouterr()

    code = main([str(tmp_path), "--baseline", str(baseline)])
    out = capsys.readouterr().out
    assert code == 0
    assert "0 recognized constants found" in out


def test_new_finding_not_in_baseline_still_reported(tmp_path, capsys):
    (tmp_path / "p.py").write_text("R = 0.017453292519943295\n")
    baseline = tmp_path / "baseline.json"
    main([str(tmp_path), "--baseline", str(baseline), "--update-baseline"])
    capsys.readouterr()

    (tmp_path / "p.py").write_text(
        "R = 0.017453292519943295\nE = 2.718281828459045\n"
    )
    code = main([str(tmp_path), "--baseline", str(baseline)])
    out = capsys.readouterr().out
    assert code == 1
    assert "2.718281828459045" in out
    assert "0.017453292519943295" not in out  # still baselined


def test_baseline_survives_line_number_drift(tmp_path, capsys):
    # the whole point of keying on (file, literal, form) instead of line:
    # unrelated lines added above must not un-baseline an existing finding
    (tmp_path / "p.py").write_text("R = 0.017453292519943295\n")
    baseline = tmp_path / "baseline.json"
    main([str(tmp_path), "--baseline", str(baseline), "--update-baseline"])
    capsys.readouterr()

    (tmp_path / "p.py").write_text(
        "# a new comment\n# another one\nR = 0.017453292519943295\n"
    )
    code = main([str(tmp_path), "--baseline", str(baseline)])
    out = capsys.readouterr().out
    assert code == 0
    assert "0 recognized constants found" in out


def test_missing_baseline_file_means_nothing_baselined(tmp_path, capsys):
    (tmp_path / "p.py").write_text("R = 0.017453292519943295\n")
    code = main([str(tmp_path), "--baseline", str(tmp_path / "nope.json")])
    assert code == 1
    assert "pi/180" in capsys.readouterr().out


def test_update_baseline_without_baseline_path_errors(tmp_path, capsys):
    code = main([str(tmp_path), "--update-baseline"])
    assert code == 2
    assert "requires --baseline" in capsys.readouterr().err
