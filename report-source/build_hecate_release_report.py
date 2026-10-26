"""Render the Hecate report from the verified evidence package.

No model inference or new timing measurements. The tile diagrams are generated
by the packaged scheduler; the numerical tables come from saved trial results.
"""
import base64
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "submissions/hecate-regional-reader-repeated-v3"
DEST = ROOT / "submissions/hecate-submission-note-v6"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DEST.mkdir(exist_ok=True)
    assets = DEST / "assets"
    assets.mkdir(exist_ok=True)
    if not (DEST / "evidence").exists():
        shutil.copytree(SOURCE, DEST / "evidence", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    originals = [p for p in SOURCE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    for p in originals:
        assert sha(p) == sha(DEST / "evidence" / p.relative_to(SOURCE)), p
    data = json.loads((SOURCE / "repeatability/view-data.json").read_text())
    r = data[0]
    raw = np.frombuffer(base64.b64decode(r["ctfield"]), dtype=np.uint8).reshape(r["field_shape"])
    arrays = {key: np.frombuffer(base64.b64decode(value), dtype=np.uint8).reshape(r["shape"])
              for key, value in r["arrays"].items()}
    x0, y0, x1, y1 = r["roi"]
    old_full = np.load(SOURCE / "outputs/case-00/full.npy")[y0:y1, x0:x1]
    naive = np.load(SOURCE / "outputs/case-00/naive.npy")
    assert np.array_equal(old_full, arrays["full"])
    assert np.array_equal(arrays["full"], arrays["regional"])
    assert np.array_equal(arrays["full"], arrays["halo"])
    assert np.count_nonzero(old_full != naive) == 3944
    for name in ("full", "regional", "halo"):
        Image.fromarray(arrays[name]).save(assets / f"{name}.png")
    Image.fromarray(naive).save(assets / "tight-crop.png")
    Image.fromarray(np.abs(arrays["full"].astype(np.int16) - arrays["regional"])).convert("L").save(assets / "difference.png")

    spec = importlib.util.spec_from_file_location("packaged_hecate_roi", SOURCE / "src/hecate_roi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = module.schedule((64, 512, 512), (64, 256, 256), (144, 144, 208, 208), batch_size=1)
    all_origins = [(y, x) for y in module.axis_starts(512, 256, 128)
                   for x in module.axis_starts(512, 256, 128)]
    selected = [tuple(v) for group in plan["groups"] for v in group["origins"]]
    assert len(all_origins) == 9 and len(selected) == 4
    assert plan["temporary_2d_bytes"] == r["accumulator_bytes"]["regional"]
    assert plan["read_context_xyxy"] == r["context"]

    # Exact CT display pixels with explicit geometric overlays; no synthetic ink.
    for filename, origins, accumulator in [
        ("full-plan.png", all_origins, (0, 0, 512, 512)),
        ("crop-plan.png", selected, tuple(r["context"])),
        ("regional-plan.png", selected, tuple(r["roi"])),
    ]:
        image = Image.fromarray(raw).convert("RGB")
        draw = ImageDraw.Draw(image)
        for y, x in origins:
            draw.rectangle((x + 1, y + 1, min(510, x + 254), min(510, y + 254)), outline="#419bcb", width=2)
            draw.ellipse((x + 5, y + 5, x + 12, y + 12), fill="#9cd8ff")
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline="#ffb447", width=5)
        image.save(assets / filename)
        # A coordinate-scale diagram of accumulation extents, separate from CT.
        extent = Image.new("RGB", (512, 512), "white")
        d = ImageDraw.Draw(extent)
        ax0, ay0, ax1, ay1 = accumulator
        d.rectangle((ax0, ay0, ax1 - 1, ay1 - 1), fill="#d7e6ed", outline="#406c80", width=3)
        d.rectangle((x0, y0, x1 - 1, y1 - 1), outline="#a75c00", width=5)
        extent.save(assets / filename.replace("plan", "storage"))

    example = []
    for key, label in [("full", "Full supplied field"), ("halo", "Aligned context crop"), ("regional", "Regional interface")]:
        s = r["statistics"][key + "_seconds"]
        tiles = r["statistics"][key + "_tiles"]["median"]
        example.append('<tr>' + ''.join([
            f'<th scope="row">{label}</th>', f'<td>{int(tiles)}</td>',
            f'<td>{s["median"]:.3f}<br><span class="range">({s["minimum"]:.3f}–{s["maximum"]:.3f})</span></td>',
            f'<td>{r["accumulator_bytes"][key] // 1024:,} KiB</td>', '<td>0</td>']) + '</tr>')
    rows = []
    for q in data:
        s = q["statistics"]
        cells = [q["sample"], str(q["sampling"]), q["region"],
                 f'{s["full_over_regional"]["median"]:.3f}',
                 f'{s["regional_over_halo"]["median"]:.3f}',
                 f'{s["halo_over_regional_accumulator"]["median"]:.2f}×', '0']
        rows.append('<tr>' + ''.join('<td>' + html.escape(c) + '</td>' for c in cells) + '</tr>')
    template = (ROOT / "src/templates/hecate_release_report.html").read_text()
    template = template.replace("__EXAMPLE_ROWS__", ''.join(example)).replace("__ALL_ROWS__", ''.join(rows))
    (DEST / "index.html").write_text(template)
    (DEST / "START_HERE.html").write_text(template)
    provenance = {
        "scope": "Figures and tables derived from the saved scientific evidence.",
        "source_package": SOURCE.name,
        "source_archive_sha256": "ab142e4141f1543d8126536d513661a618dd601b44bd412485ea3a4c7fc0cc39",
        "unchanged_evidence_files": len(originals),
        "plan": plan,
        "image_notes": "Saved uint8 predictions displayed directly as grayscale. CT uses the existing v3 display-normalized plane 32/64. Blue rectangles mark 256x256 model windows, orange marks the requested ROI. Storage diagrams show the recorded array extents at a common coordinate scale, not measured model RAM.",
        "assets": {str(p.relative_to(DEST)): sha(p) for p in sorted(assets.glob("*.png"))},
    }
    (DEST / "figure-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"website": str(DEST / "index.html"), "evidence_files": len(originals), "plan_tiles": [len(all_origins), len(selected)], "new_model_runs": 0}))


if __name__ == "__main__":
    main()
