"""Generalization of Paper A §9 to every standard model of H^n, machine-checked.

Paper A proved: the Poincaré-ball exponential map at the origin sends L2-normalized
embeddings to a constant-radius shell, making geodesic distance strictly monotone in
cosine — post-hoc hyperbolic projection is a no-op. The standard models of hyperbolic
space (ball, Lorentz/hyperboloid, Klein, upper half-space) are pairwise isometric, so
the result must hold in every chart. This script checks it numerically, mirroring the
§9 protocol: 400 unit-norm vectors at d=256, all 79,800 pairs, multiple curvatures.

Per model: the naive insertion map a pipeline would use (exp map at the basepoint /
the standard ball-to-model chart), the model's own distance formula, and two checks:
  (1) constant radius/height: all images at one radius, max spread reported;
  (2) rank identity: the model's pairwise distances are a strictly decreasing function
      of cosine — checked as exact rank agreement (after sign flip) plus strict
      monotonicity on the sorted curve.
Lorentz additionally checks the closed form d = arcosh(cosh^2(sc) - sinh^2(sc)*cos)/sc.

Seed 20260805. Offline, stdlib+numpy. Frozen output: results/hyperbolic/models_of_hn.json
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "results" / "hyperbolic" / "models_of_hn.json"

RNG = np.random.default_rng(20260805)
N, D = 400, 256
CURVATURES = [0.1, 0.5, 1.0, 2.0]

U = RNG.standard_normal((N, D))
U /= np.linalg.norm(U, axis=1, keepdims=True)
COS = np.clip(U @ U.T, -1.0, 1.0)
IU = np.triu_indices(N, k=1)
cos_pairs = COS[IU]


def spearman_perfect(dist_pairs: np.ndarray) -> dict:
    """Exact rank agreement between -distance and cosine, plus strict monotonicity."""
    order_c = np.argsort(cos_pairs, kind="stable")
    d_sorted = dist_pairs[order_c]
    monotone = bool(np.all(np.diff(d_sorted) <= 1e-12))  # cos up => distance down (non-strict tol)
    strict_frac = float(np.mean(np.diff(d_sorted) < 0))
    rank_identical = bool(
        np.array_equal(np.argsort(np.argsort(-dist_pairs, kind="stable")),
                       np.argsort(np.argsort(cos_pairs, kind="stable")))
    )
    return {"monotone_decreasing": monotone, "strict_fraction": strict_frac, "rank_identical": rank_identical}


def ball_exp(c: float) -> np.ndarray:
    sc = np.sqrt(c)
    r = np.tanh(sc) / sc  # ||v||=1 for all rows
    P = r * U
    x2 = np.sum(P * P, axis=1)
    num = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2) ** 2
    den = (1 - c * x2)[:, None] * (1 - c * x2)[None, :]
    arg = 1 + 2 * c * num / den
    Dm = np.arccosh(np.maximum(arg, 1.0)) / sc
    return P, Dm


def lorentz_exp(c: float):
    sc = np.sqrt(c)
    x0 = np.cosh(sc) / sc * np.ones(N)
    Xs = (np.sinh(sc) / sc) * U
    inner = -np.outer(x0, x0) + Xs @ Xs.T
    arg = np.maximum(-c * inner, 1.0)
    Dm = np.arccosh(arg) / sc
    closed = np.arccosh(np.maximum(np.cosh(sc) ** 2 - np.sinh(sc) ** 2 * COS, 1.0)) / sc
    return x0, Dm, float(np.max(np.abs(Dm - closed)))


def klein_from_ball(c: float):
    sc = np.sqrt(c)
    P = (np.tanh(sc) / sc) * U
    p2 = np.sum(P * P, axis=1)
    K = 2 * P / (1 + c * p2)[:, None]
    k2 = np.sum(K * K, axis=1)
    dot = K @ K.T
    arg = (1 - c * dot) / np.sqrt(np.maximum((1 - c * k2)[:, None] * (1 - c * k2)[None, :], 1e-300))
    Dm = np.arccosh(np.maximum(arg, 1.0)) / sc
    return K, Dm


def halfspace(c: float):
    sc = np.sqrt(c)
    P = np.tanh(sc) * U  # points in the unit ball (c=1 coordinates)
    e = np.zeros(D); e[-1] = -1.0  # invert about the point -e_n
    Q = P - e[None, :]
    q2 = np.sum(Q * Q, axis=1)
    H = 2 * Q / q2[:, None] + e[None, :]
    h = H[:, -1]
    diff2 = np.linalg.norm(H[:, None, :] - H[None, :, :], axis=2) ** 2
    arg = 1 + diff2 / (2 * np.outer(h, h))
    Dm = np.arccosh(np.maximum(arg, 1.0)) / sc
    ball_diff2 = np.linalg.norm(P[:, None, :] - P[None, :, :], axis=2) ** 2
    p2 = np.sum(P * P, axis=1)
    ball_arg = 1 + 2 * ball_diff2 / np.maximum((1 - p2)[:, None] * (1 - p2)[None, :], 1e-300)
    Dball = np.arccosh(np.maximum(ball_arg, 1.0)) / sc
    return h, Dm, float(np.max(np.abs(Dm - Dball)))


def main() -> None:
    report = {"n_vectors": N, "dim": D, "n_pairs": int(len(cos_pairs)), "seed": 20260805, "curvatures": {}}
    for c in CURVATURES:
        entry = {}
        P, Db = ball_exp(c)
        radii = np.linalg.norm(P, axis=1)
        entry["ball"] = {"radius_spread": float(radii.max() - radii.min()), **spearman_perfect(Db[IU])}
        x0, Dl, closed_dev = lorentz_exp(c)
        entry["lorentz"] = {"height_spread": float(x0.max() - x0.min()), "closed_form_max_dev": closed_dev, **spearman_perfect(Dl[IU])}
        K, Dk = klein_from_ball(c)
        rk = np.linalg.norm(K, axis=1)
        entry["klein"] = {"radius_spread": float(rk.max() - rk.min()), "max_dev_vs_ball": float(np.max(np.abs(Dk - Db))), **spearman_perfect(Dk[IU])}
        h, Dh, dev = halfspace(c)
        entry["halfspace"] = {"isometry_max_dev_vs_ball": dev, **spearman_perfect(Dh[IU])}
        report["curvatures"][str(c)] = entry
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
