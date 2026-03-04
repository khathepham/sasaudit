"""
conftest.py — pytest configuration

WeasyPrint requires Cairo (a system C library) to be installed. Since we never
call PDF-generation code in tests, we stub out the weasyprint module here so
that importing sasaudit doesn't fail on machines without Cairo.
"""

import sys
from unittest.mock import MagicMock

# Stub out weasyprint and its Cairo dependency before sasaudit is imported
for mod in ("weasyprint", "cairocffi"):
    sys.modules.setdefault(mod, MagicMock())