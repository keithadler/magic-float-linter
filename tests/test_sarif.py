import json

from exact_linter.cli import main


def test_sarif_output_structure(tmp_path, capsys):
    (tmp_path / "p.py").write_text(
        "FULL = 3.141592653589793\nSHORT = 3.14159\n"
    )
    code = main([str(tmp_path), "--format", "sarif", "--exit-zero"])
    assert code == 0
    doc = json.loads(capsys.readouterr().out)

    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "exact"
    rule_ids = {rule["id"] for rule in run["tool"]["driver"]["rules"]}
    assert rule_ids == {"recognized-constant", "truncated-constant", "recognized-sequence"}

    results = run["results"]
    assert len(results) == 2
    by_rule = {r["ruleId"]: r for r in results}
    assert by_rule["recognized-constant"]["level"] == "note"
    assert by_rule["truncated-constant"]["level"] == "warning"
    assert "lost digits" in by_rule["truncated-constant"]["message"]["text"]

    location = results[0]["locations"][0]["physicalLocation"]
    assert location["artifactLocation"]["uri"].endswith("p.py")
    assert location["region"]["startLine"] in (1, 2)
    assert location["region"]["startColumn"] >= 1


def test_sarif_empty_findings_is_valid(tmp_path, capsys):
    (tmp_path / "clean.py").write_text("x = 1\n")
    main([str(tmp_path), "--format", "sarif"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["runs"][0]["results"] == []
