"""
Path Generator — Stochastic path generation for Monte Carlo simulations.

Generates price paths using various stochastic models:
GBM, Heston, Jump-Diffusion, and custom processes.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class PathConfig:
    """Configuration for path generation."""
    model: str = "gbm"
    initial_price: float = 100.0
    drift: float = 0.08
    volatility: float = 0.20
    num_steps: int = 252
    dt: Optional[float] = None  # auto-computed as 1/num_steps
    # Heston parameters
    kappa: float = 2.0  # mean reversion speed
    theta: float = 0.04  # long-run variance
    xi: float = 0.5  # vol of vol
    rho: float = -0.7  # correlation
    # Jump parameters
    jump_intensity: float = 2.0
    jump_mean: float = -0.02
    jump_std: float = 0.04
    # Seed
    seed: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PathGenerator:
    """
    Stochastic path generator for Monte Carlo simulations.

    Supports:
    - Geometric Brownian Motion (GBM)
    - Heston stochastic volatility model
    - Merton jump-diffusion model
    - Custom user-defined generators

    Usage::

        gen = PathGenerator()
        await gen.initialize()
        paths = gen.generate_gbm(S0=100, mu=0.08, sigma=0.20, steps=252, paths=1000)
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the path generator."""
        self._initialized = True

    # ---- GBM ----

    def generate_gbm(
        self,
        S0: float = 100.0,
        mu: float = 0.08,
        sigma: float = 0.20,
        steps: int = 252,
        paths: int = 1,
        dt: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> list[list[float]]:
        """
        Generate Geometric Brownian Motion paths.

        dS = μ·S·dt + σ·S·dW
        S_t = S_0 · exp((μ - σ²/2)·t + σ·√t·ε)
        """
        rng = random.Random(seed or self._seed or 42)
        dt_val = dt or (1.0 / steps)
        drift = (mu - sigma ** 2 / 2) * dt_val
        diffusion = sigma * math.sqrt(dt_val)

        all_paths: list[list[float]] = []
        for _ in range(paths):
            path = [S0]
            S = S0
            for _ in range(steps):
                z = rng.gauss(0, 1)
                S *= math.exp(drift + diffusion * z)
                path.append(S)
            all_paths.append(path)

        return all_paths

    # ---- Heston ----

    def generate_heston(
        self,
        S0: float = 100.0,
        v0: float = 0.04,
        mu: float = 0.08,
        kappa: float = 2.0,
        theta: float = 0.04,
        xi: float = 0.5,
        rho: float = -0.7,
        steps: int = 252,
        paths: int = 1,
        dt: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> list[list[float]]:
        """
        Generate paths using the Heston stochastic volatility model.

        dS = μ·S·dt + √v·S·dW₁
        dv = κ·(θ - v)·dt + ξ·√v·dW₂
        corr(dW₁, dW₂) = ρ
        """
        rng = random.Random(seed or self._seed or 42)
        dt_val = dt or (1.0 / steps)

        all_paths: list[list[float]] = []
        for _ in range(paths):
            path = [S0]
            S = S0
            v = max(v0, 0)
            for _ in range(steps):
                z1 = rng.gauss(0, 1)
                z2 = rng.gauss(0, 1)
                w1 = z1
                w2 = rho * z1 + math.sqrt(1 - rho ** 2) * z2

                v = max(0, v + kappa * (theta - v) * dt_val + xi * math.sqrt(max(v, 0) * dt_val) * w2)
                S *= math.exp((mu - v / 2) * dt_val + math.sqrt(max(v, 0) * dt_val) * w1)
                path.append(S)
            all_paths.append(path)

        return all_paths

    # ---- Jump-Diffusion ----

    def generate_jump_diffusion(
        self,
        S0: float = 100.0,
        mu: float = 0.08,
        sigma: float = 0.20,
        jump_intensity: float = 2.0,
        jump_mean: float = -0.02,
        jump_std: float = 0.04,
        steps: int = 252,
        paths: int = 1,
        dt: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> list[list[float]]:
        """
        Generate Merton jump-diffusion paths.

        dS/S = (μ - λ·k)·dt + σ·dW + (J - 1)·dN
        """
        rng = random.Random(seed or self._seed or 42)
        dt_val = dt or (1.0 / steps)

        # Jump compensator
        k = math.exp(jump_mean + jump_std ** 2 / 2) - 1
        drift_adj = mu - jump_intensity * k

        all_paths: list[list[float]] = []
        for _ in range(paths):
            path = [S0]
            S = S0
            for _ in range(steps):
                z = rng.gauss(0, 1)
                S *= math.exp(
                    (drift_adj - sigma ** 2 / 2) * dt_val
                    + sigma * math.sqrt(dt_val) * z
                )

                # Poisson jump
                n_jumps = sum(1 for _ in range(int(jump_intensity * dt_val * 10000)) if rng.random() < 0.0001)
                for _ in range(n_jumps):
                    J = math.exp(rng.gauss(jump_mean, jump_std))
                    S *= J

                path.append(S)
            all_paths.append(path)

        return all_paths

    # ---- Utility ----

    def compute_statistics(self, paths: list[list[float]]) -> dict[str, Any]:
        """Compute statistics across multiple paths."""
        terminal_values = [p[-1] for p in paths]
        n = len(terminal_values)

        mean = sum(terminal_values) / n
        variance = sum((v - mean) ** 2 for v in terminal_values) / (n - 1) if n > 1 else 0
        std = math.sqrt(variance)

        sorted_vals = sorted(terminal_values)
        median = sorted_vals[n // 2]
        p5 = sorted_vals[int(n * 0.05)]
        p95 = sorted_vals[int(n * 0.95)]

        return {
            "num_paths": n,
            "mean": round(mean, 2),
            "std": round(std, 2),
            "median": round(median, 2),
            "p5": round(p5, 2),
            "p95": round(p95, 2),
            "min": round(sorted_vals[0], 2),
            "max": round(sorted_vals[-1], 2),
        }

    def generate_custom(
        self,
        generator: Callable[[float, int, random.Random], list[float]],
        S0: float = 100.0,
        steps: int = 252,
        paths: int = 1,
        seed: Optional[int] = None,
    ) -> list[list[float]]:
        """Generate paths using a custom generator function."""
        rng = random.Random(seed or self._seed or 42)
        all_paths = []
        for _ in range(paths):
            path = generator(S0, steps, rng)
            all_paths.append(path)
        return all_paths
