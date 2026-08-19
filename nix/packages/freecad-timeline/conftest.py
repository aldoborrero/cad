# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make the addon importable and force Qt offscreen for the test run."""

import os
import sys

ADDON_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
if ADDON_DIRECTORY not in sys.path:
    sys.path.insert(0, ADDON_DIRECTORY)

# Any Qt test must run headlessly; set this before a QApplication exists.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
