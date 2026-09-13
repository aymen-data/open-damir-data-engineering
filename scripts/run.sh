#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export POLARS_MAX_THREADS="${POLARS_MAX_THREADS:-4}"
if [ "$#" -eq 0 ]; then set -- 202501; fi
"${PYTHON:-python3}" -m damir.cli --root "$project_root" run --months "$@"
