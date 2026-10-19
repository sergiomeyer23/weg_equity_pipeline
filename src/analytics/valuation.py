"""DCF valuation model for WEGE3.SA."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class Assumptions:
    years: int = 5
    growth: List[float] = field(default_factory=lambda: [0.08, 0.07, 0.06, 0.06, 0.05])
    ebit_margin: float = 0.170
    tax: float = 0.210
    da_ratio: float = 0.035
    capex_ratio: float = 0.047
    wc_ratio: float = 0.020
    term_growth: float = 0.045
    rf: float = 0.1175
    erp: float = 0.055
    beta: float = 0.95
    debt_spread: float = 0.025
    tax_rate: float = 0.210
    # target_debt_v = share of debt in total capital (D/V). D/V = 0.15 ~= D/E = 0.176.
    target_debt_v: float = 0.15


@dataclass
class DCFResult:
    target_price: float
    ev: float
    equity: float
    wacc: float
    ke: float
    kd_at: float
    terminal: float
    pv_terminal: float
    pv_explicit: float
    fcf: List[float]
    rev: List[float]
    dfs: List[float]


class DCF:
    def __init__(self, a: Optional[Assumptions] = None) -> None:
        self.a = a or Assumptions()

    def ke(self, rf: Optional[float] = None, b: Optional[float] = None) -> float:
        rf = self.a.rf if rf is None else rf
        b = self.a.beta if b is None else b
        return rf + b * self.a.erp

    def kd(self, rf: Optional[float] = None) -> float:
        rf = self.a.rf if rf is None else rf
        return rf + self.a.debt_spread

    def kd_after_tax(self, rf: Optional[float] = None) -> float:
        return self.kd(rf) * (1.0 - self.a.tax_rate)

    def wacc(self, rf: Optional[float] = None, b: Optional[float] = None, d: Optional[float] = None) -> float:
        ke = self.ke(rf, b)
        kd = self.kd_after_tax(rf)
        d = self.a.target_debt_v if d is None else d
        return ke * (1.0 - d) + kd * d

    def run(
        self,
        base_rev: float,
        base_fcf: Optional[float] = None,
        net_debt: float = 0.0,
        shares: float = 1.0,
        intl_share: float = 0.40,
        fx: Optional[float] = None,
        fx_base: float = 5.10,
        rf: Optional[float] = None,
    ) -> DCFResult:
        a = self.a
        fx = fx if fx is not None else fx_base
        fx_f = fx / fx_base
        dom = 1.0 - intl_share

        rev = base_rev
        revs: List[float] = []
        fcfs: List[float] = []
        for g in a.growth[: a.years]:
            rev = rev * (1.0 + g) * (dom + intl_share * fx_f) / (dom + intl_share)
            revs.append(rev)
            ebit = rev * a.ebit_margin
            nopat = ebit * (1.0 - a.tax)
            da = rev * a.da_ratio
            capex = rev * a.capex_ratio
            wc = rev * a.wc_ratio
            fcfs.append(nopat + da - capex - wc)

        w = self.wacc(rf)
        if w <= a.term_growth:
            raise ValueError(f"WACC ({w:.2%}) must exceed terminal growth ({a.term_growth:.2%}).")
        disc = [(1.0 + w) ** -(i + 1) for i in range(len(fcfs))]
        pv_exp = sum(c * d for c, d in zip(fcfs, disc))
        term = fcfs[-1] * (1.0 + a.term_growth) / (w - a.term_growth)
        pv_term = term * disc[-1]

        ev = pv_exp + pv_term
        eq = ev - net_debt
        price = eq / shares if shares else float("nan")
        return DCFResult(price, ev, eq, w, self.ke(rf), self.kd_after_tax(rf), term, pv_term, pv_exp, fcfs, revs, disc)

    def grid(
        self,
        base_rev: float,
        base_fcf: float,
        net_debt: float,
        shares: float,
        intl_share: float,
        fxs: List[float],
        selics: List[float],
        fx_base: float = 5.10,
    ) -> pd.DataFrame:
        recs: List[Dict[str, Any]] = []
        for s in selics:
            for x in fxs:
                r = self.run(base_rev, base_fcf, net_debt, shares, intl_share, x, fx_base, rf=s)
                recs.append({"selic": s, "fx": x, "wacc": r.wacc, "price": r.target_price})
        df = pd.DataFrame(recs)
        return df.pivot(index="selic", columns="fx", values="price").sort_index(ascending=False)


def bridge(r: DCFResult) -> pd.DataFrame:
    adj = r.equity - r.ev  # > 0 with net cash, < 0 with net debt
    return pd.DataFrame([
        ("PV of explicit FCFF", r.pv_explicit),
        ("PV of terminal value", r.pv_terminal),
        ("Enterprise value", r.ev),
        ("Net cash" if adj >= 0 else "Net debt", adj),
        ("Equity value", r.equity),
    ], columns=["item", "value"])


def tornado(
    a: Assumptions,
    base_rev: float,
    net_debt: float,
    shares: float,
    intl_share: float,
    fx_base: float = 5.10,
) -> pd.DataFrame:
    """Target-price impact of flexing one assumption at a time (low/high)."""
    from dataclasses import replace

    def price(**kw: Any) -> float:
        fx = kw.pop("fx", None)
        return DCF(replace(a, **kw)).run(base_rev, None, net_debt, shares, intl_share, fx, fx_base).target_price

    base = price()
    shocks = [
        ("EBIT margin ±3 pp", price(ebit_margin=a.ebit_margin - 0.03), price(ebit_margin=a.ebit_margin + 0.03)),
        ("Selic ±2.5 pp", price(rf=a.rf + 0.025), price(rf=a.rf - 0.025)),
        ("Terminal growth ±1 pp", price(term_growth=a.term_growth - 0.01), price(term_growth=a.term_growth + 0.01)),
        ("Beta ±0.2", price(beta=a.beta + 0.2), price(beta=a.beta - 0.2)),
        ("Capex ±1 pp of revenue", price(capex_ratio=a.capex_ratio + 0.01), price(capex_ratio=a.capex_ratio - 0.01)),
        ("USD/BRL 4.40 / 5.80", price(fx=4.40), price(fx=5.80)),
    ]
    df = pd.DataFrame(shocks, columns=["driver", "low", "high"])
    df["base"] = base
    df["range"] = (df["high"] - df["low"]).abs()
    return df.sort_values("range", ascending=True).reset_index(drop=True)
