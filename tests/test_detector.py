import jax
import jax.numpy as jnp
import numpy as np

import cryojax.simulator as cs
from cryojax.image import irfftn, rfftn


def test_gaussian_limit():
    # Pick a large integrated electron flux to test
    # Create InstrumentConfig, picking a large electron flux to test
    config = cs.InstrumentConfig(
        (25, 25),
        1.0,
        voltage_in_kilovolts=300.0,
        electrons_per_angstrom_squared=10000.0,
    )
    N_pix = np.prod(config.padded_shape)
    electrons_per_pixel = config.electrons_per_angstrom_squared * config.pixel_size**2
    # Create squared wavefunction of just vacuum, i.e. 1 everywhere
    vacuum_squared_wavefunction = jnp.ones(config.shape, dtype=float)
    fourier_vacuum_squared_wavefunction = rfftn(vacuum_squared_wavefunction)
    # Create detector models
    key = jax.random.PRNGKey(1234)
    dqe = cs.IdealDQE()
    gaussian_detector = cs.GaussianDetector(dqe)
    poisson_detector = cs.PoissonDetector(dqe)
    # Compute detector readout
    fourier_gaussian_detector_readout = gaussian_detector.compute_detector_readout(
        key,
        fourier_vacuum_squared_wavefunction,
        config,
    )
    fourier_poisson_detector_readout = poisson_detector.compute_detector_readout(
        key,
        fourier_vacuum_squared_wavefunction,
        config,
    )
    # Compare to see if the autocorrelation has converged
    np.testing.assert_allclose(
        irfftn(
            jnp.abs(fourier_gaussian_detector_readout) ** 2
            / (N_pix * electrons_per_pixel**2),
            s=config.padded_shape,
        ),
        irfftn(
            jnp.abs(fourier_poisson_detector_readout) ** 2
            / (N_pix * electrons_per_pixel**2),
            s=config.padded_shape,
        ),
        rtol=1e-2,
    )
