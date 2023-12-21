"""
Atomic-based electron density representations.
"""

from __future__ import annotations

__all__ = ["AtomCloud"]

from typing import Type, Any

import equinox as eqx
from jaxtyping import Array

from ._electron_density import ElectronDensity
from ..pose import Pose
from ...core import field


class AtomCloud(ElectronDensity):
    """
    Abstraction of a point cloud of atoms.
    """

    weights: Array = field()
    coordinates: Array = field()
    variances: Array = field()
    identity: Array = field()

    is_real: bool = field(default=True, static=True)

    def __check_init__(self):
        if self.is_real is False:
            raise NotImplementedError(
                "Fourier atomic densities are not supported."
            )

    def rotate_to(self, pose: Pose) -> AtomCloud:
        coordinates = pose.rotate(self.coordinates, is_real=self.is_real)
        return eqx.tree_at(lambda d: d.coordinates, self, coordinates)

    @classmethod
    def from_file(
        cls: Type[AtomCloud],
        filename: str,
        config: dict = {},
        **kwargs: Any,
    ) -> AtomCloud:
        """
        Load an Atom Cloud

        TODO: What is the file format appropriate here? Q. for Michael...
        """
        raise NotImplementedError
        # return cls.from_mrc(filename, config=config, **kwargs)

    @classmethod
    def from_stack(
        cls: Type["AtomCloud"], stack: list["AtomCloud"]
    ) -> "AtomCloud":
        """
        Stack a list of electron densities along the leading
        axis of a single electron density.
        """
        raise NotImplementedError

    def __getitem__(self, key: int) -> "AtomCloud":
        """Get a particular electron density in the electron density stack."""
        raise NotImplementedError
