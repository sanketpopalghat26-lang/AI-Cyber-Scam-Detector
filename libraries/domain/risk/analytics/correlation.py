"""Asset Correlation calculation using Decimal."""

import math
from decimal import Decimal
from typing import Dict, List, Sequence


def calculate_correlation_matrix(
    asset_returns: Dict[str, Sequence[Decimal]],
) -> Dict[str, Dict[str, Decimal]]:
    """Calculate pairwise Pearson correlation matrix across asset return series."""
    symbols = list(asset_returns.keys())
    matrix: Dict[str, Dict[str, Decimal]] = {s1: {} for s1 in symbols}

    for i, s1 in enumerate(symbols):
        matrix[s1][s1] = Decimal("1.0")
        for j in range(i + 1, len(symbols)):
            s2 = symbols[j]
            r1 = asset_returns[s1]
            r2 = asset_returns[s2]

            min_len = min(len(r1), len(r2))
            if min_len < 2:
                matrix[s1][s2] = Decimal("0")
                matrix[s2][s1] = Decimal("0")
                continue

            v1 = list(r1[:min_len])
            v2 = list(r2[:min_len])

            n = Decimal(str(min_len))
            m1 = sum(v1, Decimal("0")) / n
            m2 = sum(v2, Decimal("0")) / n

            cov = sum((a - m1) * (b - m2) for a, b in zip(v1, v2)) / (n - Decimal("1"))
            var1 = sum((a - m1) ** Decimal("2") for a in v1) / (n - Decimal("1"))
            var2 = sum((b - m2) ** Decimal("2") for b in v2) / (n - Decimal("1"))

            if var1 <= Decimal("0") or var2 <= Decimal("0"):
                corr = Decimal("0")
            else:
                std1 = Decimal(str(math.sqrt(float(var1))))
                std2 = Decimal(str(math.sqrt(float(var2))))
                corr = cov / (std1 * std2)

            # Clamp between -1 and 1
            corr = max(Decimal("-1.0"), min(Decimal("1.0"), corr))
            matrix[s1][s2] = corr
            matrix[s2][s1] = corr

    return matrix
