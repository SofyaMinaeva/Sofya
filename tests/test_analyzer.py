import json
from pathlib import Path

from analyzer import analyze_360_report, build_manager_report_markdown


def test_analysis_and_report_generation():
    payload = json.loads(Path("examples/sample_report.json").read_text(encoding="utf-8"))
    answers = [
        line.strip()
        for line in Path("examples/sample_answers.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    analysis = analyze_360_report(payload, answers)
    assert analysis.overall_score > 0
    assert analysis.decision_recommendation
    assert len(analysis.competency_results) == 4

    report = build_manager_report_markdown(analysis)
    assert "# Отчет по 360 для руководителя" in report
    assert "## 4. Кадровая рекомендация" in report
