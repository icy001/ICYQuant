"""Live trading support for ICYQuant (post-revival, 2026-11-12).

Contains only what the shadow-trading phase needs:
- m5_reversal_signal.py : bit-exact replica of the exp04 H12_down signal
- shadow_runner.py      : tails MT5-exported M1 bars, emits live signals
"""
