"""The `vision.describe` capability: one image out, one description back.

Risk is WRITE with reversible False, and that pairing is the whole gate.
READ is not a lighter class for the same operation, it is the operation with
three mechanisms removed at once: `ToolSpec.approval_required` is
`risk in {WRITE, HIGH_IMPACT}`, so no card; `presence.decide` returns RUN for
READ before it ever reaches the reversibility branch, so no confirm; and
`AgentRuntime.run_next` writes the durable effect intent and receipt only when
`spec.approval_required`, so no receipt either. A frame leaving the host for a
third party with no card, no confirm and no receipt is the wrong trade, and
`services/devon/commands.py` already wrote down why: screens hold secrets.

Not HIGH_IMPACT, because `approval_required` is identical for both and that
class is short for a reason: every member changes durable state on a remote
system. Describing an image changes nothing anywhere. `reversible=False` is
what does the work here, and it is the truth: no later action recalls bytes
already sent.

On demand only. Nothing here caches a frame, holds one between calls, or
starts anything that runs on its own.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    require_approved_runtime_binding,
)
from services.agent_runtime.tools import ToolRegistry, ToolResult, ToolRisk, ToolSpec
from services.devon.approval import ApprovalQueue
from services.vision.base import (
    DEFAULT_MAX_IMAGE_BYTES,
    ImageSource,
    VisionProvider,
    VisionRequest,
)

# Extension to media type. An extension this map does not know is refused
# rather than guessed, because guessing sends bytes to a vendor that will
# reject them after the account has already been charged for the attempt.
_EXTENSIONS = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_DEFAULT_PROMPT = (
    "Describe this image precisely. If it shows an error, a dashboard or a "
    "screen, read back the exact text that matters and say what is wrong. "
    "Describe only what is visible and say so when something is unreadable."
)


class VisionAdapter:
    """Registers `vision.describe` against an approval authority."""

    def __init__(
        self,
        approvals: Optional[ApprovalQueue],
        *,
        provider_factory: Callable[[], VisionProvider],
        image_root: Optional[str] = None,
        max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
        max_output_tokens: Optional[int] = None,
    ) -> None:
        self.approvals = approvals
        self._provider_factory = provider_factory
        self._image_root = image_root
        self._max_image_bytes = max_image_bytes
        self._max_output_tokens = max_output_tokens

    def register(self, registry: ToolRegistry) -> None:
        registry.register(
            ToolSpec(
                name="vision.describe",
                parameters=("image_path", "prompt"),
                description=(
                    "Send ONE image file to the configured vision backend and "
                    "return a text description of it. Approval gated and "
                    "irreversible: the bytes leave this host and no later "
                    "action recalls them, and an image of a screen or a desk "
                    "can carry a credential, a contract or a person. Reads "
                    "only from the configured image root; the backend is not "
                    "selectable per call."
                ),
                risk=ToolRisk.WRITE,
                handler=self._describe,
                reversible=False,
                blast_radius=(
                    "one image file transmitted to the configured vision "
                    "backend; the disclosure is permanent"
                ),
            )
        )

    # -- the handler ------------------------------------------------------

    async def _describe(self, arguments: Dict[str, Any]) -> ToolResult:
        args = dict(arguments)
        metadata = args.pop(APPROVAL_METADATA_KEY, None)

        if self.approvals is None:
            return ToolResult(
                False,
                error=(
                    "no approval authority is configured, so sending a frame "
                    "off this host is refused"
                ),
            )

        try:
            request_id, _binding = require_approved_runtime_binding(
                self.approvals,
                metadata,
                tool_name="vision.describe",
                arguments=args,
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))

        loaded = self._load(args.get("image_path"))
        if isinstance(loaded, ToolResult):
            return loaded

        provider = self._provider_factory()
        # The second guard. A backend can be swapped by configuration between
        # the card and the call, and a text only backend must refuse rather
        # than send a frame it cannot read.
        if not getattr(provider, "supports_images", False):
            return ToolResult(
                False,
                error=(
                    f"the configured vision backend '{getattr(provider, 'name', '?')}' "
                    "does not accept images; nothing was sent"
                ),
            )

        prompt = str(args.get("prompt") or "").strip() or _DEFAULT_PROMPT
        answer = await provider.describe(
            VisionRequest(
                image=loaded, prompt=prompt, max_tokens=self._output_budget()
            )
        )

        # Flat and non secret. `sanitize_receipt_payload` strips by exact
        # lowercase key name and does NOT recurse, so nothing nested goes in
        # here, and no base64 ever does.
        return ToolResult(
            True,
            output=answer.text,
            metadata={
                "provider": answer.provider,
                "model": answer.model,
                "image_sha256": loaded.digest,
                "image_bytes": loaded.byte_count,
                "image_media_type": loaded.media_type,
                "latency_ms": answer.latency_ms,
                "input_tokens": answer.usage.input_tokens,
                "output_tokens": answer.usage.output_tokens,
                # A cut off description reads exactly like a finished one, so
                # the receipt says which it was rather than leaving the reader
                # to infer it from the length.
                "truncated": answer.truncated,
                "provider_receipt_id": request_id,
            },
        )

    # -- loading, with the root as the only door --------------------------

    def _output_budget(self) -> int:
        """How many output tokens one description may cost.

        Read at call time, like the root, so a deployment can raise it without
        a code change when a model's thinking eats the allowance.
        """
        if self._max_output_tokens is not None:
            return int(self._max_output_tokens)
        from app.core.config import settings

        return int(settings.VISION_MAX_OUTPUT_TOKENS)

    def _root(self) -> str:
        if self._image_root is not None:
            return str(self._image_root).strip()
        from app.core.config import settings

        return str(settings.VISION_IMAGE_ROOT or "").strip()

    def _load(self, raw_path: Any):
        root_value = self._root()
        if not root_value:
            return ToolResult(
                False,
                error=(
                    "VISION_IMAGE_ROOT is not set, so there is no directory "
                    "this tool is allowed to read from and every call is "
                    "refused. Set it to the one directory images arrive in."
                ),
            )

        root = Path(root_value)
        if not root.is_dir():
            return ToolResult(
                False,
                error=f"VISION_IMAGE_ROOT does not exist or is not a directory: {root}",
            )

        candidate = str(raw_path or "").strip()
        if not candidate:
            return ToolResult(False, error="image_path is required")
        if os.path.isabs(candidate):
            return ToolResult(
                False,
                error=(
                    "image_path must be relative to VISION_IMAGE_ROOT; "
                    "absolute paths are refused"
                ),
            )

        root_resolved = root.resolve()
        target = (root_resolved / candidate).resolve()
        if root_resolved != target and root_resolved not in target.parents:
            return ToolResult(
                False,
                error="image_path escapes VISION_IMAGE_ROOT; refused",
            )
        if not target.is_file():
            return ToolResult(False, error=f"no such image under the root: {candidate}")

        media_type = _EXTENSIONS.get(target.suffix.lower())
        if media_type is None:
            return ToolResult(
                False,
                error=(
                    f"unsupported image extension '{target.suffix or 'none'}'; "
                    f"allowed: {', '.join(sorted(_EXTENSIONS))}"
                ),
            )

        data = target.read_bytes()
        try:
            return ImageSource.from_bytes(
                data, media_type=media_type, max_bytes=self._max_image_bytes
            )
        except ValueError as exc:
            return ToolResult(False, error=str(exc))
