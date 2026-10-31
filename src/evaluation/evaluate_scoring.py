"""
Measures how well the LLM scores match your own judgement.

  python -m src.evaluation.evaluate_scoring export data/eval_labels.csv
      Writes the scored jobs to a CSV. Fill the empty "label" column: 1 = you'd apply, 0 = you wouldn't.
      Aim for 30 to 50 labelled jobs. Rows left empty are ignored.

  python -m src.evaluation.evaluate_scoring report data/eval_labels.csv
      Prints precision@k and the rank correlation between scores and labels.
"""
import csv
import sys

from src.db.seen_jobs import all_seen

FIELDS = ["key", "title", "url", "score", "label"]


def precision_at_k(rows: list[dict], k: int) -> float:
    """The share of the k highest-scored jobs that you labelled as worth applying to."""
    top = sorted(rows, key=lambda row: row["score"], reverse=True)[:k]
    return sum(row["label"] for row in top) / len(top)


def _ranks(values: list[float]) -> list[float]:
    """Ranks starting at 1, where tied values share their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for position in range(i, j + 1):
            ranks[order[position]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    """Rank correlation from -1 to 1. Returns None if either list has only one distinct value."""
    rx, ry = _ranks(xs), _ranks(ys)
    mean_x, mean_y = sum(rx) / len(rx), sum(ry) / len(ry)
    covariance = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return covariance / (var_x * var_y) ** 0.5


def export_labels(path: str) -> int:
    jobs = all_seen()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({**job, "label": ""} for job in jobs)
    return len(jobs)


def load_labels(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return [
            {"score": int(row["score"]), "label": int(row["label"])}
            for row in csv.DictReader(f)
            if row["label"].strip()
        ]


def report(path: str) -> None:
    rows = load_labels(path)
    if not rows:
        print("No labelled rows found. Fill the label column first.")
        return
    print(f"Labelled jobs: {len(rows)}, worth applying to: {sum(row['label'] for row in rows)}")
    for k in (5, 10, 20):
        if k <= len(rows):
            print(f"Precision@{k}: {precision_at_k(rows, k):.2f}")
    correlation = spearman([row["score"] for row in rows], [row["label"] for row in rows])
    print("Spearman: not defined (all scores or labels are the same)" if correlation is None
          else f"Spearman: {correlation:.2f}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("export", "report"):
        sys.exit(__doc__)
    if sys.argv[1] == "export":
        print(f"Wrote {export_labels(sys.argv[2])} jobs to {sys.argv[2]}")
    else:
        report(sys.argv[2])
