"""Write the generated OpenAPI 3.1 document to docs/api/openapi.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lifeexe  # noqa: E402
import lifeexe.api.routes  # noqa: E402,F401
from lifeexe.api.registry import api  # noqa: E402
from lifeexe.core.config import REPO_DIR  # noqa: E402

out = REPO_DIR / "docs" / "api" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
spec = api.openapi("LIFE.EXE API", lifeexe.__version__)
out.write_text(json.dumps(spec, indent=2) + "\n")
print(f"wrote {out} ({len(spec['paths'])} paths)")
