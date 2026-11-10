"""The train/validation split for the learned model (#297 step 3).

FRED series cluster by family (a curve of maturities, an FX panel, a release's
components), so a split by series id would leak a family's shape from train
into validation. The split is by `fred_universe.family(sid)`: every series in
a family lands on the same side, chosen by the parity of a CRC of the family
key, so it is stable across runs and machines and needs no file. On the
weekly corpus this gives 686 families, 1,491 train and 1,522 validation
series. GIFT remains the clean test (no FRED series in it).

    split_of("DGS10") -> "train" | "valid"
"""
from __future__ import annotations

import os
import sys
import re
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fred_universe as fu  # noqa: E402


_M4 = re.compile(r"^H[0-9]+$")   # M4 hourly ids only (FRED has M1, M2)


def split_of(sid: str) -> str:
    # M4 ids (H1..H414 etc.) are independent series that the FRED family key
    # would lump into one family; split those by the id itself
    key = sid if _M4.match(sid) else fu.family(sid)
    return "valid" if zlib.crc32(key.encode()) % 2 else "train"
