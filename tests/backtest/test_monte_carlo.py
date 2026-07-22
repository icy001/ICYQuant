from services.backtest import (
    BootstrapSampler,
)


def test_bootstrap_sampler():

    sampler = BootstrapSampler()

    result = sampler.sample(
        [1, 2, 3, 4]
    )

    assert len(result) == 4