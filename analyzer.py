from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Any, Iterable


@dataclass
class CompetencyResult:
    name: str
    overall_score: float
    self_score: float | None
    manager_score: float | None
    peers_score: float | None
    reports_score: float | None
    external_score: float | None
    spread: float
    sentiment: str
    confidence: str


@dataclass
class AnalysisResult:
    employee: dict[str, Any]
    competency_results: list[CompetencyResult]
    overall_score: float
    top_strengths: list[str]
    top_risks: list[str]
    decision_recommendation: str
    decision_rationale: list[str]
    development_plan: list[dict[str, str]]
    summary: str


POSITIVE_WORDS = {
    "сильный",
    "сильная",
    "сильные",
    "лидер",
    "вовлекает",
    "эффективно",
    "профессионал",
    "надежный",
    "рост",
    "развитие",
    "инициатива",
    "ответственный",
    "проактивный",
    "качественно",
    "быстро",
}

NEGATIVE_WORDS = {
    "слабый",
    "проблема",
    "конфликт",
    "срыв",
    "риски",
    "недостаточно",
    "медленно",
    "ошибки",
    "неуверенно",
    "не хватает",
    "выгорание",
    "стресс",
    "неясно",
    "жалобы",
}


def _safe_mean(values: Iterable[float]) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def _extract_scores_by_group(raw_competency: dict[str, Any]) -> dict[str, list[float]]:
    """
    Supports two common schemas:
    1) {"ratings": [{"group":"self", "score":4.1}, ...]}
    2) {"scores": {"self":4.0, "manager":3.7, ...}}
    """
    grouped: dict[str, list[float]] = {
        "self": [],
        "manager": [],
        "peers": [],
        "reports": [],
        "external": [],
    }

    if isinstance(raw_competency.get("ratings"), list):
        for item in raw_competency["ratings"]:
            group = str(item.get("group", "")).lower()
            score = item.get("score")
            if group in grouped and isinstance(score, (int, float)):
                grouped[group].append(float(score))

    scores_map = raw_competency.get("scores")
    if isinstance(scores_map, dict):
        for group, score in scores_map.items():
            group_norm = str(group).lower()
            if group_norm in grouped and isinstance(score, (int, float)):
                grouped[group_norm].append(float(score))

    return grouped


def _sentiment_for_competency(name: str, text_answers: list[str]) -> str:
    name_low = name.lower()
    related = [t.lower() for t in text_answers if name_low in t.lower()]
    if not related:
        related = [t.lower() for t in text_answers]

    pos = sum(sum(1 for word in POSITIVE_WORDS if word in text) for text in related)
    neg = sum(sum(1 for word in NEGATIVE_WORDS if word in text) for text in related)

    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _confidence(spread: float, points_count: int) -> str:
    if points_count <= 2:
        return "low"
    if spread > 1.0:
        return "low"
    if spread > 0.6:
        return "medium"
    return "high"


def analyze_360_report(payload: dict[str, Any], text_answers: list[str]) -> AnalysisResult:
    employee = payload.get("employee") if isinstance(payload.get("employee"), dict) else {}
    competencies = payload.get("competencies") if isinstance(payload.get("competencies"), list) else []

    results: list[CompetencyResult] = []

    for comp in competencies:
        if not isinstance(comp, dict):
            continue
        name = str(comp.get("name", "Без названия"))
        grouped = _extract_scores_by_group(comp)
        all_scores = [value for arr in grouped.values() for value in arr]
        overall = _safe_mean(all_scores)
        spread = pstdev(all_scores) if len(all_scores) > 1 else 0.0
        sentiment = _sentiment_for_competency(name, text_answers)

        result = CompetencyResult(
            name=name,
            overall_score=round(overall, 2),
            self_score=round(_safe_mean(grouped["self"]), 2) if grouped["self"] else None,
            manager_score=round(_safe_mean(grouped["manager"]), 2) if grouped["manager"] else None,
            peers_score=round(_safe_mean(grouped["peers"]), 2) if grouped["peers"] else None,
            reports_score=round(_safe_mean(grouped["reports"]), 2) if grouped["reports"] else None,
            external_score=round(_safe_mean(grouped["external"]), 2) if grouped["external"] else None,
            spread=round(spread, 2),
            sentiment=sentiment,
            confidence=_confidence(spread, len(all_scores)),
        )
        results.append(result)

    overall_score = round(_safe_mean([r.overall_score for r in results]), 2)

    sorted_by_score = sorted(results, key=lambda r: r.overall_score, reverse=True)
    top_strengths = [r.name for r in sorted_by_score[:3] if r.overall_score >= 3.8]
    top_risks = [r.name for r in sorted(results, key=lambda r: r.overall_score)[:3] if r.overall_score < 3.4]

    decision_recommendation, rationale = _decision_logic(overall_score, results)
    development_plan = _build_development_plan(results)
    summary = _build_summary(overall_score, top_strengths, top_risks, decision_recommendation)

    return AnalysisResult(
        employee=employee,
        competency_results=results,
        overall_score=overall_score,
        top_strengths=top_strengths,
        top_risks=top_risks,
        decision_recommendation=decision_recommendation,
        decision_rationale=rationale,
        development_plan=development_plan,
        summary=summary,
    )


def _decision_logic(overall_score: float, results: list[CompetencyResult]) -> tuple[str, list[str]]:
    high = sum(1 for r in results if r.overall_score >= 4.2)
    low = sum(1 for r in results if r.overall_score < 3.3)
    high_spread = sum(1 for r in results if r.spread > 0.9)

    rationale = [
        f"Итоговый балл по компетенциям: {overall_score:.2f}/5.",
        f"Сильных компетенций (>=4.2): {high}.",
        f"Зон риска (<3.3): {low}.",
        f"Компетенций с высоким расхождением оценок (>0.9): {high_spread}.",
    ]

    if overall_score >= 4.2 and low == 0:
        return "Рассмотреть расширение зоны ответственности / продвижение", rationale
    if overall_score >= 3.7 and low <= 1:
        return "Сохранить в роли, утвердить целевой план развития", rationale
    if overall_score >= 3.3:
        return "План развития с контрольной точкой через 3 месяца", rationale
    return "Performance improvement plan (PIP) с ежемесячным мониторингом", rationale


def _build_development_plan(results: list[CompetencyResult]) -> list[dict[str, str]]:
    weak = sorted(results, key=lambda r: r.overall_score)[:3]
    plan: list[dict[str, str]] = []

    for comp in weak:
        action = (
            "Коучинг с руководителем + практический проект"
            if comp.overall_score < 3.5
            else "Точечное развитие через stretch-задачу"
        )
        target = f"Поднять оценку по '{comp.name}' минимум на 0.4 пункта"
        metric = "Повторная mini-360 + подтверждение результата в KPI"
        timeline = "90 дней"
        plan.append(
            {
                "competency": comp.name,
                "action": action,
                "target": target,
                "metric": metric,
                "timeline": timeline,
            }
        )
    return plan


def _build_summary(overall: float, strengths: list[str], risks: list[str], decision: str) -> str:
    strengths_text = ", ".join(strengths) if strengths else "ярко выраженные сильные стороны не выявлены"
    risks_text = ", ".join(risks) if risks else "критичные зоны риска отсутствуют"
    return (
        f"Сотрудник демонстрирует общий уровень {overall:.2f}/5. "
        f"Сильные стороны: {strengths_text}. "
        f"Зоны развития: {risks_text}. "
        f"Рекомендация: {decision}."
    )


def build_manager_report_markdown(analysis: AnalysisResult) -> str:
    employee_name = analysis.employee.get("name", "Не указано")
    role = analysis.employee.get("role", "Не указано")
    department = analysis.employee.get("department", "Не указано")

    lines = [
        "# Отчет по 360 для руководителя",
        "",
        "## 1. Паспорт оценки",
        f"- Сотрудник: **{employee_name}**",
        f"- Роль: **{role}**",
        f"- Подразделение: **{department}**",
        f"- Итоговый балл: **{analysis.overall_score:.2f}/5**",
        "",
        "## 2. Executive Summary",
        analysis.summary,
        "",
        "## 3. Анализ по компетенциям",
        "| Компетенция | Общий балл | Self | Manager | Peers | Reports | External | Разброс | Sentiment | Доверие |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]

    for r in analysis.competency_results:
        lines.append(
            f"| {r.name} | {r.overall_score:.2f} | {fmt(r.self_score)} | {fmt(r.manager_score)} | "
            f"{fmt(r.peers_score)} | {fmt(r.reports_score)} | {fmt(r.external_score)} | {r.spread:.2f} | {r.sentiment} | {r.confidence} |"
        )

    lines.extend(
        [
            "",
            "## 4. Кадровая рекомендация",
            f"**{analysis.decision_recommendation}**",
            "",
            "### Обоснование",
        ]
    )
    lines.extend([f"- {item}" for item in analysis.decision_rationale])

    lines.extend(
        [
            "",
            "## 5. План развития (90 дней)",
            "| Компетенция | Действие | Цель | Метрика | Срок |",
            "|---|---|---|---|---|",
        ]
    )

    for step in analysis.development_plan:
        lines.append(
            f"| {step['competency']} | {step['action']} | {step['target']} | {step['metric']} | {step['timeline']} |"
        )

    return "\n".join(lines) + "\n"


def fmt(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "-"
