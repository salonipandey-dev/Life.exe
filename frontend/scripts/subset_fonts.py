"""Subset the two OFL typefaces to Latin and write WOFF files (zlib, no brotli needed).

Run once when fonts change:  python3 scripts/subset_fonts.py <path-to-ofl-dir>
"""
import sys
from pathlib import Path

from fontTools import subset

SRC = Path(sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/truetype/google-fonts/ofl")
OUT = Path(__file__).resolve().parents[1] / "public" / "fonts"
UNICODES = "U+0000-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2000-206F,U+20B9,U+2122,U+2190-2193,U+2212,U+2215,U+25A0-25FF,U+2713"

JOBS = {
    "cardo/Cardo-Regular.ttf": "cardo-regular.woff",
    "cardo/Cardo-Italic.ttf": "cardo-italic.woff",
    "cardo/Cardo-Bold.ttf": "cardo-bold.woff",
    "dmsans/DMSans[opsz,wght].ttf": "dmsans-variable.woff",
}

OUT.mkdir(parents=True, exist_ok=True)
for src, dst in JOBS.items():
    opts = subset.Options()
    opts.flavor = "woff"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    font = subset.load_font(str(SRC / src), opts)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=subset.parse_unicodes(UNICODES))
    sub.subset(font)
    subset.save_font(font, str(OUT / dst), opts)
    print(dst, (OUT / dst).stat().st_size)
for lic in ("cardo", "dmsans"):
    (OUT / f"OFL-{lic}.txt").write_text((SRC / lic / "OFL.txt").read_text())
