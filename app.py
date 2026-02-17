from __future__ import annotations

import argparse
import json
from pathlib import Path

from analyzer import analyze_360_report, build_manager_report_markdown


def determine_report_format() -> str:
    return """# Формат отчета для руководителя

1. Паспорт оценки: сотрудник, роль, подразделение, общий балл.
2. Executive Summary: 4-5 предложений с выводом о готовности к кадровому решению.
3. Анализ компетенций:
   - общий балл по компетенции,
   - срезы по группам (self/manager/peers/reports/external),
   - разброс оценок (сигнал согласованности),
   - тональность текстовых комментариев.
4. Кадровая рекомендация:
   - решение (продвижение / в роли + развитие / PIP),
   - обоснование через количественные показатели.
5. План развития на 90 дней:
   - 2-3 приоритетных компетенции,
   - конкретные действия,
   - целевые метрики,
   - срок ревью.

Этот формат ориентирован на принятие кадровых решений и запуск персонального плана развития.
"""


def read_text_answers(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Анализатор результатов 360")
    parser.add_argument("--report", required=True, help="Путь к JSON отчету 360")
    parser.add_argument("--answers", required=True, help="Путь к txt с текстовыми ответами")
    parser.add_argument(
        "--output",
        default="manager_report.md",
        help="Куда сохранить итоговый отчет для руководителя",
    )
    parser.add_argument(
        "--format-only",
        action="store_true",
        help="Только вывести рекомендуемый формат отчета",
    )
    args = parser.parse_args()

    if args.format_only:
        print(determine_report_format())
        return

    payload = json.loads(Path(args.report).read_text(encoding="utf-8"))
    text_answers = read_text_answers(Path(args.answers))

    analysis = analyze_360_report(payload, text_answers)
    report_md = build_manager_report_markdown(analysis)
    Path(args.output).write_text(report_md, encoding="utf-8")

    print(determine_report_format())
    print(f"\nГотово: отчет сохранен в {args.output}")


if __name__ == "__main__":
    main()
