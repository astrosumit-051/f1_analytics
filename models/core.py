"""Model definitions and fitting for the undercut window (issue A3, #11).

Two kinds of fit:

* Plain logistic regression (the gap-only baseline).
* Logistic regression with a race random intercept, fitted by maximum likelihood
  with Gauss-Hermite quadrature over the intercept (the primary model).

Predictions are always for a *new* race: the random intercept is integrated out,
p = E_z[expit(x b + sigma z)], z ~ N(0, 1). This is the right probability for a pit
wall facing a race the model has not seen, and the same rule is used for training,
tuning, test and grid rows so the numbers are comparable.

Everything a model learns from data (spline knots, feature centring and scaling,
the imputation value for a missing tyre-age difference) is learnt from the rows it
is fitted on, so the race bootstrap can refit it on any resample.

Needs numpy, pandas and scipy only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, log_expit

GH_NODES = 25
_Z, _W = np.polynomial.hermite_e.hermegauss(GH_NODES)
_W = _W / _W.sum()  # weights for E over N(0, 1)

OUTCOMES = ("success_h3", "success_h0", "success_h5", "success_common_h3")


# --------------------------------------------------------------------------- spline
def natural_spline_knots(x: np.ndarray, df: int = 3) -> np.ndarray:
    """df + 1 knots at evenly spaced quantiles (boundary knots at the 0 and 100%)."""
    return np.quantile(np.asarray(x, float), np.linspace(0, 1, df + 1))


def natural_spline_basis(x: np.ndarray, knots: np.ndarray) -> np.ndarray:
    """Natural cubic spline basis without intercept (ESL eq. 5.4-5.5).

    Columns: x, then K - 2 nonlinear terms, so df = len(knots) - 1. Linear beyond
    the boundary knots.
    """
    x = np.asarray(x, float)
    k = np.asarray(knots, float)
    K = len(k)

    def d(j):
        return (np.clip(x - k[j], 0, None) ** 3 - np.clip(x - k[K - 1], 0, None) ** 3) / (k[K - 1] - k[j])

    cols = [x]
    last = d(K - 2)
    for j in range(K - 2):
        cols.append(d(j) - last)
    return np.column_stack(cols)


# --------------------------------------------------------------------------- specs
@dataclass(frozen=True)
class Spec:
    model_id: str
    numeric: tuple[str, ...] = ()           # linear terms
    delay_terms: bool = False                # d23 main effect and d23 x gap (linear)
    era: bool = False                        # post2022 indicator
    random_intercept: bool = False
    spline_df: int = 3
    description: str = ""


PRIMARY_FEATURES = (
    "tyre_age_diff",
    "circuit_pitlane_median_sec",
    "rejoin_traffic_cars",
    "cars_between_at_ref",
    "overtaking_difficulty",
)

SPECS: dict[str, Spec] = {
    "baseline_gap_v1": Spec(
        "baseline_gap_v1",
        description="Gap only: natural spline in gap (3 df), plain logistic. 4 parameters.",
    ),
    "primary_v1": Spec(
        "primary_v1",
        numeric=PRIMARY_FEATURES,
        delay_terms=True,
        random_intercept=True,
        description=(
            "Natural spline in gap (3 df), d23 shift and d23 x gap slope, tyre-age difference, "
            "circuit pit-lane median, projected rejoin traffic, cars between, overtaking "
            "difficulty, race random intercept. 11 fixed effects + 1 variance."
        ),
    ),
}


# --------------------------------------------------------------------------- design
@dataclass
class Design:
    spec: Spec
    knots: np.ndarray = field(default=None)
    centre: dict = field(default_factory=dict)
    scale: dict = field(default_factory=dict)
    impute: dict = field(default_factory=dict)
    names: list = field(default_factory=list)

    @classmethod
    def learn(cls, spec: Spec, rows: pd.DataFrame) -> "Design":
        d = cls(spec)
        gap = rows["gap_before_sec"].astype(float).to_numpy()
        d.knots = natural_spline_knots(gap, spec.spline_df)
        for col in spec.numeric:
            v = pd.to_numeric(rows[col], errors="coerce")
            d.impute[col] = float(v.median())
            v = v.fillna(d.impute[col])
            d.centre[col] = float(v.mean())
            d.scale[col] = float(v.std()) or 1.0
        d.centre["gap"] = float(gap.mean())
        d.names = d._names()
        return d

    def _names(self):
        n = ["intercept"] + [f"gap_ns{i + 1}" for i in range(self.spec.spline_df)]
        if self.spec.delay_terms:
            n += ["d23", "d23_x_gap"]
        if self.spec.era:
            n += ["post2022"]
        n += [f"{c}_z" for c in self.spec.numeric]
        return n

    def matrix(self, rows: pd.DataFrame) -> np.ndarray:
        gap = rows["gap_before_sec"].astype(float).to_numpy()
        basis = natural_spline_basis(gap, self.knots)
        # scale basis columns to similar size for the optimiser (fixed transform)
        basis = basis / np.array([3.0] + [10.0] * (basis.shape[1] - 1))
        cols = [np.ones(len(rows)), *basis.T]
        if self.spec.delay_terms:
            d23 = rows["delay_group"].eq("d23").to_numpy(float)
            cols += [d23, d23 * (gap - self.centre["gap"])]
        if self.spec.era:
            cols.append(rows["era"].eq("post2022").to_numpy(float))
        for c in self.spec.numeric:
            v = pd.to_numeric(rows[c], errors="coerce").fillna(self.impute[c]).to_numpy(float)
            cols.append((v - self.centre[c]) / self.scale[c])
        return np.column_stack(cols)


# --------------------------------------------------------------------------- fitting
@dataclass
class Fit:
    spec: Spec
    design: Design
    beta: np.ndarray
    sigma: float
    cov: np.ndarray | None
    loglik: float
    n: int
    races: int
    converged: bool

    def predict(self, rows: pd.DataFrame) -> np.ndarray:
        eta = self.design.matrix(rows) @ self.beta
        if self.sigma <= 0:
            return expit(eta)
        return expit(eta[:, None] + self.sigma * _Z[None, :]) @ _W

    def coefficients(self) -> pd.DataFrame:
        se = np.sqrt(np.diag(self.cov))[: len(self.beta)] if self.cov is not None else np.full(len(self.beta), np.nan)
        out = pd.DataFrame({"term": self.design.names, "estimate": self.beta, "std_error": se})
        if self.spec.random_intercept:
            out.loc[len(out)] = ["race_sd", self.sigma, np.nan]
        return out


def _negll_glm(beta, X, y):
    eta = X @ beta
    ll = y * log_expit(eta) + (1 - y) * log_expit(-eta)
    grad = X.T @ (y - expit(eta))
    return -ll.sum(), -grad


def _negll_glmm(theta, X, y, groups, n_groups):
    beta, log_sigma = theta[:-1], theta[-1]
    sigma = np.exp(log_sigma)
    eta = (X @ beta)[:, None] + sigma * _Z[None, :]            # n x Q
    ll_i = y[:, None] * log_expit(eta) + (1 - y[:, None]) * log_expit(-eta)
    ll_g = np.zeros((n_groups, GH_NODES))
    np.add.at(ll_g, groups, ll_i)
    a = ll_g + np.log(_W)[None, :]
    m = a.max(axis=1, keepdims=True)
    lse = m[:, 0] + np.log(np.exp(a - m).sum(axis=1))
    post = np.exp(a - lse[:, None])                            # posterior node weights per group
    resid = y[:, None] - expit(eta)                            # n x Q
    w_i = post[groups]                                         # n x Q
    g_beta = X.T @ (w_i * resid).sum(axis=1)
    g_ls = (w_i * resid * _Z[None, :]).sum() * sigma
    return -lse.sum(), -np.append(g_beta, g_ls)


def _numeric_hessian(f, x, eps=1e-5):
    k = len(x)
    H = np.zeros((k, k))
    for i in range(k):
        e = np.zeros(k)
        e[i] = eps
        H[:, i] = (f(x + e)[1] - f(x - e)[1]) / (2 * eps)
    return (H + H.T) / 2


def fit(spec: Spec, rows: pd.DataFrame, outcome: str) -> Fit:
    rows = rows.dropna(subset=[outcome])
    y = rows[outcome].astype(float).to_numpy()
    if len(np.unique(y)) < 2:
        raise ValueError("Need both outcome classes to fit.")
    design = Design.learn(spec, rows)
    X = design.matrix(rows)
    races = rows["event_id"].astype(str)
    if spec.random_intercept:
        codes, uniq = pd.factorize(races)
        f = lambda t: _negll_glmm(t, X, y, codes, len(uniq))
        start = np.append(np.zeros(X.shape[1]), np.log(0.5))
    else:
        f = lambda t: _negll_glm(t, X, y)
        start = np.zeros(X.shape[1])
    res = minimize(f, start, jac=True, method="BFGS", options={"maxiter": 2000, "gtol": 1e-6})
    converged = bool(np.isfinite(res.fun) and (res.success or np.max(np.abs(res.jac)) < 1e-3))
    if spec.random_intercept and not converged:
        # BFGS can step the log race SD to overflow on an odd bootstrap resample; retry
        # with the SD bounded to [0.00005, 20] (log scale), which leaves interior optima unchanged.
        bounds = [(None, None)] * X.shape[1] + [(np.log(5e-5), np.log(20.0))]
        res = minimize(f, start, jac=True, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 5000, "gtol": 1e-6})
        converged = bool(np.isfinite(res.fun) and (res.success or np.max(np.abs(res.jac)) < 1e-3))
    theta = res.x
    try:
        cov = np.linalg.inv(_numeric_hessian(f, theta))
    except np.linalg.LinAlgError:
        cov = None
    if spec.random_intercept:
        beta, sigma = theta[:-1], float(np.exp(theta[-1]))
        if sigma < 1e-4:
            sigma = 0.0
    else:
        beta, sigma = theta, 0.0
    return Fit(spec, design, beta, sigma, cov, -float(res.fun), len(rows), races.nunique(), converged)
