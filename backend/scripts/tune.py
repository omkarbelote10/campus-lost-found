"""Sweep scoring configurations against the labelled benchmark.

Measures rather than guesses. Reports Recall@1 / MRR (ranking quality) and the
best achievable F1 with its threshold (classification quality) for each variant.

    docker exec campus-lost-found-backend-1 python scripts/tune.py
"""

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402

from app.services.embeddings import build_item_text, get_embedder  # noqa: E402
from scripts.benchmark import LEVELS, NOW, OBJECTS, UPLOADS, ZONE, reshoot  # noqa: E402
from app.utils.validators import extract_ocr_tokens  # noqa: E402


def cos(a, b):
    if a is None or b is None:
        return 0.0
    return max(0.0, sum(x * y for x, y in zip(a, b)))


def calibrate(score, floor, ceil):
    """Raw cosine from these models is not spread over [0,1] -- the informative
    band is narrow (DINOv2 puts unrelated objects around 0.5 and the same object
    around 0.9). Rescaling that band to [0,1] is what lets a weighted sum and a
    fixed threshold actually discriminate."""
    if score <= floor:
        return 0.0
    if score >= ceil:
        return 1.0
    return (score - floor) / (ceil - floor)


def build_cases():
    """Precompute embeddings once: (query_name, level, {gallery_name: (v, t)})."""
    e = get_embedder()
    gallery = {}
    for name, spec in OBJECTS.items():
        gallery[name] = (
            e.embed_image(str(UPLOADS / spec["file"])),
            e.embed_text(build_item_text("Found item", spec["found"], "ELECTRONICS", ZONE)),
            extract_ocr_tokens(spec["found"]),
        )

    cases = []
    for name, spec in OBJECTS.items():
        base = Image.open(UPLOADS / spec["file"]).convert("RGB")
        qt = e.embed_text(build_item_text("Lost item", spec["lost"], "ELECTRONICS", ZONE))
        qo = extract_ocr_tokens(spec["lost"])
        for level in LEVELS:
            qv = e.embed_image(reshoot(base, level))
            sims = {
                g: (cos(qv, gv), cos(qt, gt), bool(set(qo) & set(go)))
                for g, (gv, gt, go) in gallery.items()
            }
            cases.append((name, level, sims))
    return cases


def evaluate(cases, w_v, w_t, w_c, vis_cal, txt_cal):
    hits = rr = 0
    true_s, false_s = [], []
    for truth, _level, sims in cases:
        ranked = []
        for gname, (v, t, ocr) in sims.items():
            vv = calibrate(v, *vis_cal) if vis_cal else v
            tt = calibrate(t, *txt_cal) if txt_cal else t
            total = w_v * vv + w_t * tt + w_c * 1.0 + (0.25 if ocr else 0.0)
            total = min(1.0, max(0.0, total))
            ranked.append((total, gname))
        ranked.sort(reverse=True)
        rank = [g for _, g in ranked].index(truth) + 1
        hits += rank == 1
        rr += 1 / rank
        for s, g in ranked:
            (true_s if g == truth else false_s).append(s)

    best = (0.0, 0.0, 0.0, 0.0)
    for i in range(0, 101):
        th = i / 100
        tp = sum(s >= th for s in true_s)
        fp = sum(s >= th for s in false_s)
        rec = tp / len(true_s)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        if f1 > best[0]:
            best = (f1, th, prec, rec)
    n = len(cases)
    return hits / n, rr / n, best


def main() -> int:
    cases = build_cases()
    print(f"{len(cases)} queries x {len(OBJECTS)} gallery items\n")

    VC, TC = (0.50, 0.95), (0.55, 0.95)
    variants = [
        ("current: .45v .30t .25cat, raw", 0.45, 0.30, 0.25, None, None),
        ("drop category: .60v .40t, raw", 0.60, 0.40, 0.0, None, None),
        ("drop category: .60v .40t, calibrated", 0.60, 0.40, 0.0, VC, TC),
        ("drop category: .50v .50t, calibrated", 0.50, 0.50, 0.0, VC, TC),
        ("drop category: .70v .30t, calibrated", 0.70, 0.30, 0.0, VC, TC),
        ("drop category: .80v .20t, calibrated", 0.80, 0.20, 0.0, VC, TC),
        ("visual only, calibrated", 1.0, 0.0, 0.0, VC, TC),
        ("text only, calibrated", 0.0, 1.0, 0.0, VC, TC),
    ]

    print(f"{'variant':<40} {'R@1':>6} {'MRR':>7} {'bestF1':>7} {'@th':>5} {'prec':>6} {'rec':>6}")
    print("-" * 82)
    for label, wv, wt, wc, vc, tc in variants:
        r1, mrr, (f1, th, prec, rec) = evaluate(cases, wv, wt, wc, vc, tc)
        print(f"{label:<40} {r1*100:5.1f}% {mrr:7.4f} {f1:7.3f} {th:5.2f} "
              f"{prec*100:5.1f}% {rec*100:5.1f}%")

    print("\n=== weight sweep, calibrated, no category ===")
    print(f"{'w_visual':>9} {'w_text':>7} {'R@1':>6} {'MRR':>7} {'bestF1':>7} {'@th':>5}")
    best_cfg = None
    for i in range(0, 11):
        wv = i / 10
        r1, mrr, (f1, th, prec, rec) = evaluate(cases, wv, 1 - wv, 0.0, VC, TC)
        print(f"{wv:9.1f} {1-wv:7.1f} {r1*100:5.1f}% {mrr:7.4f} {f1:7.3f} {th:5.2f}")
        if best_cfg is None or (f1, r1) > (best_cfg[0], best_cfg[1]):
            best_cfg = (f1, r1, wv, th)
    print(f"\nbest: w_visual={best_cfg[2]:.1f} w_text={1-best_cfg[2]:.1f} "
          f"F1={best_cfg[0]:.3f} at threshold {best_cfg[3]:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
