"""Ladder ablation on the out-of-development holdout corpus.

Same six nested pools and scoring as ladder_ablation.py, run over the 300
least-popular FRED daily-universe series in data_holdout/, none of which were
ever fetched or used while the grammar was developed.

    PYTHONPATH=src python benchmarks/ladder_holdout.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fred
fred._CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data_holdout")

import ladder_ablation as LA
LA.OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ladder_holdout.csv")

if __name__ == "__main__":
    LA.main()
