"""Retrieval accuracy for the matching pipeline.

Builds a labelled benchmark from the real uploaded photos: each object appears
once in the FOUND gallery, and each LOST query is that same object photographed
differently, described in different words. Scores every query against every
gallery item with the production ScoringEngine, then reports ranking accuracy
and how the live thresholds classify true vs false pairs.

    docker exec campus-lost-found-backend-1 python scripts/benchmark.py
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageEnhance, ImageFilter  # noqa: E402

from app.services.embeddings import build_item_text, get_embedder  # noqa: E402
from app.services.scoring import ScoringEngine  # noqa: E402
from app.utils.validators import extract_ocr_tokens  # noqa: E402

UPLOADS = Path("backend/uploads")

# Each object: its photo, how the finder described it, how the owner described it.
# Wording deliberately differs between the two sides, as it would in reality.
OBJECTS = {
    "orange_iphone": {
        "file": "4_4acdae37cb434705bf68d0bf941d5ba6.jpg",
        "found": "Orange Apple iPhone with a matching orange case and three rear cameras",
        "lost": "I lost my orange iPhone, it has an orange silicone case on it",
    },
    "blue_motorola": {
        "file": "14_f6b371fc9dfd4e72b49740e43d666f21.webp",
        "found": "Dark blue Motorola phone with four rear camera lenses",
        "lost": "Lost a navy blue Motorola handset with four cameras on the back",
    },
    "black_motorola": {
        "file": "15_3b467c7c6ff84a408b3dc518af85f5bc.jpg",
        "found": "Black Motorola phone with a textured back and four cameras",
        "lost": "Missing my black Motorola, it has a textured rear panel",
    },
    "blue_umbrella": {
        "file": "14_ff7156bb9e3847b98b7e86a12cb8be75.webp",
        "found": "Navy blue folding umbrella with a black handle",
        "lost": "Lost my dark blue compact umbrella with a black grip",
    },
}

LEVELS = {"mild": (8, 0.9, 1.05, 0.92, 0.4),
          "moderate": (16, 0.75, 1.3, 0.82, 0.8),
          "severe": (24, 0.55, 1.9, 0.72, 1.1)}

ZONE = "Library Zone"
NOW = datetime(2026, 8, 29, 15, 0)


def reshoot(img, level):
    rot, scale, pad, bright, blur = LEVELS[level]
    bg = (118, 118, 122)
    w, h = img.size
    obj = img.crop((int(w * 0.1), int(h * 0.12), int(w * 0.9), int(h * 0.95)))
    obj = obj.rotate(rot, expand=True, fillcolor=bg)
    obj = obj.resize((max(1, int(obj.width * scale)), max(1, int(obj.height * scale))))
    canvas = Image.new("RGB", (int(obj.width * pad), int(obj.height * pad)), bg)
    canvas.paste(obj, ((canvas.width - obj.width) // 2, (canvas.height - obj.height) // 2))
    canvas = ImageEnhance.Brightness(canvas).enhance(bright)
    return canvas.filter(ImageFilter.GaussianBlur(blur))


def item(text_emb, img_emb, desc, incident, has_image=True):
    return SimpleNamespace(
        text_embedding=text_emb, image_embedding=img_emb,
        category="ELECTRONICS", campus_zone=ZONE, latitude=None, longitude=None,
        incident_time=incident, ocr_tokens=extract_ocr_tokens(desc),
        image_urls=["x.jpg"] if has_image else [],
    )


def score(lost, found):
    total, status = ScoringEngine.calculate_total_score(
        ScoringEngine.calculate_visual_score(lost.image_embedding, found.image_embedding),
        ScoringEngine.calculate_text_score(lost.text_embedding, found.text_embedding),
        ScoringEngine.calculate_category_score(lost.category, found.category),
        ScoringEngine.calculate_spatial_decay(None, None, None, None, lost.campus_zone, found.campus_zone),
        ScoringEngine.calculate_temporal_decay(lost.incident_time, found.incident_time),
        ScoringEngine.calculate_ocr_bonus(lost.ocr_tokens, found.ocr_tokens),
        has_image_1=bool(lost.image_urls), has_image_2=bool(found.image_urls),
    )
    return total, status


def main() -> int:
    e = get_embedder()

    gallery = {}
    for name, spec in OBJECTS.items():
        path = str(UPLOADS / spec["file"])
        gallery[name] = item(
            e.embed_text(build_item_text("Found item", spec["found"], "ELECTRONICS", ZONE)),
            e.embed_image(path), spec["found"], NOW,
        )

    print(f"gallery: {len(gallery)} objects | queries: {len(gallery) * len(LEVELS)}")
    print(f"image model: {e.image.model_name}   text model: {e.text.model_name}\n")

    hits = rr = 0
    n = 0
    true_scores, false_scores = [], []
    per_level = {lvl: [0, 0] for lvl in LEVELS}

    print("query                        rank  top-1 guess        score   correct-score")
    print("-" * 78)
    # Each query runs at two realistic time gaps: found within hours, and found a
    # week later. A formula whose thresholds only work same-day is not usable.
    gaps = {"6h": timedelta(hours=6), "7d": timedelta(days=7)}
    for name, spec in OBJECTS.items():
        base = Image.open(UPLOADS / spec["file"]).convert("RGB")
        for level in LEVELS:
          for gap_label, gap in gaps.items():
            q = item(
                e.embed_text(build_item_text("Lost item", spec["lost"], "ELECTRONICS", ZONE)),
                e.embed_image(reshoot(base, level)), spec["lost"],
                NOW - gap,
            )
            ranked = sorted(
                ((score(q, g)[0], gname) for gname, g in gallery.items()), reverse=True
            )
            rank = [gname for _, gname in ranked].index(name) + 1
            correct_score = next(s for s, gn in ranked if gn == name)

            n += 1
            hits += rank == 1
            rr += 1 / rank
            per_level[level][0] += rank == 1
            per_level[level][1] += 1
            for s, gname in ranked:
                (true_scores if gname == name else false_scores).append(s)

            print(f"{name + '/' + level + '/' + gap_label:<31} {rank:>2}   {ranked[0][1]:<18} "
                  f"{ranked[0][0]:.3f}   {correct_score:.3f}")

    print("\n=== RANKING ACCURACY ===")
    print(f"  Recall@1 : {hits}/{n} = {hits / n * 100:.1f}%   (random = {100 / len(gallery):.0f}%)")
    print(f"  MRR      : {rr / n:.4f}")
    for lvl, (h, t) in per_level.items():
        print(f"    {lvl:<9}: {h}/{t}")

    print("\n=== THRESHOLD BEHAVIOUR ===")
    pot, high = ScoringEngine.POTENTIAL_THRESHOLD, ScoringEngine.HIGH_CONFIDENCE_THRESHOLD
    tp = sum(s >= pot for s in true_scores)
    fp = sum(s >= pot for s in false_scores)
    print(f"  true pairs  : {len(true_scores)}  -> {tp} surfaced (recall {tp/len(true_scores)*100:.0f}%)")
    print(f"  false pairs : {len(false_scores)}  -> {fp} surfaced (false-positive rate {fp/len(false_scores)*100:.0f}%)")
    precision = tp / (tp + fp) if (tp + fp) else 0
    print(f"  precision@{pot} : {precision*100:.1f}%")
    print(f"  score range  : true {min(true_scores):.3f}-{max(true_scores):.3f} | "
          f"false {min(false_scores):.3f}-{max(false_scores):.3f}")
    print(f"  thresholds   : POTENTIAL {pot}  HIGH_CONFIDENCE {high}")

    print("\n=== THRESHOLD SWEEP (where should POTENTIAL sit?) ===")
    print("  thresh  recall  precision   F1")
    best = (0, None)
    for t in [x / 100 for x in range(50, 96, 5)]:
        tp = sum(s >= t for s in true_scores)
        fp = sum(s >= t for s in false_scores)
        rec = tp / len(true_scores)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        if f1 > best[0]:
            best = (f1, t)
        mark = "  <- current" if abs(t - pot) < 1e-9 else ""
        print(f"  {t:.2f}    {rec*100:5.1f}%  {prec*100:6.1f}%  {f1:.3f}{mark}")
    print(f"\n  best F1 at threshold {best[1]:.2f} (F1 {best[0]:.3f}), current is {pot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
