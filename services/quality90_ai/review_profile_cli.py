"""Local operator entry: actual brand profile -> Claude -> signed AI receipt.
No remote call can trigger model usage. This local command needs authorization.
The read-only n8n registry receives only signed compact metadata, not raw text.
"""

import argparse
import json
import pathlib

from claude_runner import provision_key, review_request, safe_dir
from review_core import hold
from review_gateway import bound_request
from review_registry import export_summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--root", default="/opt/devon/quality90-ai-review")
    ap.add_argument("--brands", default="/opt/creator-workspace/brands")
    a = ap.parse_args()
    try:
        path = pathlib.Path(a.input)
        if path.is_symlink() or path.stat().st_size > 100000:
            raise ValueError("unsafe request")
        raw = json.loads(path.read_text())
        root = safe_dir(a.root)
        req = bound_request(raw, a.brands)
        result = review_request(req, root)
        if result.get("modelReviewPerformed"):
            export_summary(root, result["reviewId"], provision_key(root))
            result["signedRegistryEntry"] = True
        print(json.dumps(result))
        return 0 if result.get("state") == "READY_FOR_TEE_REVIEW" else 2
    except Exception as e:
        print(
            json.dumps(
                {**hold("review input or immutable receipt failed"), "errorType": type(e).__name__}
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
