#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Testing Phase 1: Config"
python -c "from core.config import ConfigManager; print('OK', bool(ConfigManager.env_map('.env')))"

echo "Testing Phase 3/5: Auth and PIN hashing"
python -c "from core.auth import EnhancedAdminOnlyAuth; a=EnhancedAdminOnlyAuth(); print('PIN setup callable', callable(a.set_admin_pin))"

echo "Testing Phase 4: Exceptions"
python -c "from core.exceptions import JarvisError, AuthError, APIError, ResourceError, ConfigError; print('OK')"

echo "Testing Phase 6: File lock"
python - <<'PY'
from core.filelock import file_lock
import tempfile
import os

p = os.path.join(tempfile.gettempdir(), 'jarvis_test.lock')
with file_lock(p):
	print('OK')
PY

echo "Testing Phase 7: Cache cleaner"
python -c "from core.cache_cleaner import clean_all; print(type(clean_all()).__name__)"

echo "Testing Phase 8/9: Validation and Paths"
python -c "from core.validation import validate_url; from core.paths import DATA_DIR; print(validate_url('https://example.com'), bool(DATA_DIR))"

echo "All selected fix checks passed"
