"""Paper figures. Figure 2 is redrawn from the committed table (sting_results/tables/
stage_a_acceptance.csv) with the same code as sting/analysis/figures.py (title/legend overlap fixed
there too); the other figures are the committed analysis outputs, with figure 5's empty right margin
cropped. No number is computed here."""
from pathlib import Path
import sys

import pandas as pd
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1] / "llm-agent-collusion-2" / "Collusion_Liars_Bar"
sys.path.insert(0, str(ROOT))
from sting.analysis import figures as F  # noqa: E402

RES = ROOT / "sting_results"
OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

tab = pd.read_csv(RES / "tables" / "stage_a_acceptance.csv")
F.fig2_acceptance({"stage_a": tab, "primary_model": "llama-3.1-8b"}, OUT, stub=False)


def crop(src: Path, dst: Path, pad: int = 12):
    im = Image.open(src).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    x0, y0, x1, y1 = ImageChops.difference(im, bg).getbbox()
    im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad))).save(dst)


for name in ("fig1_design", "fig3_snapshots", "fig4_live", "fig5_detector"):
    crop(RES / "figures" / f"{name}.png", OUT / f"{name}.png")
crop(OUT / "fig2_acceptance.png", OUT / "fig2_acceptance.png")
print(sorted(p.name for p in OUT.iterdir()))
