"""Vercel Python entrypoint.

Vercel looks for an ASGI ``app`` in this module and routes every request here
(see vercel.json). The application itself is unchanged — this file only puts
the repository root on the import path so ``web`` and its siblings resolve.

Hosting notes for this deployment target:
- State (simulation engine, manual lab, SQLite case store) lives in the
  function instance. Cold starts reset it, and concurrent instances do not
  share it, so treat a serverless deployment as single-viewer.
- The case/audit database is written under /tmp (see config.OUTPUT_DIR) and is
  discarded with the instance.
- The Dockerfile in the repository root is the stateful, long-running way to
  host the same app when those trade-offs matter.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web import app  # noqa: E402,F401
