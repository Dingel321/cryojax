import jax.numpy as jnp
from jaxtyping import Array, Float


def convert_quaternion_to_euler_angles(
    wxyz: Float[Array, "4"], convention: str = "zyz"
) -> Float[Array, "3"]:
    """Convert a quaternion to a sequence of euler angles about an extrinsic
    coordinate system.

    Adapted from https://github.com/chrisflesher/jax-scipy-spatial/.
    """
    if len(convention) != 3 or not all([axis in ["x", "y", "z"] for axis in convention]):
        raise ValueError(
            f"`convention` should be a string of three characters, each "
            f"of which is 'x', 'y', or 'z'. Instead, got '{convention}'"
        )
    if convention[0] == convention[1] or convention[1] == convention[2]:
        raise ValueError(
            f"`convention` cannot have axes repeating in a row. For example, "
            f"'xxy' or 'zzz' are not allowed. Got '{convention}'."
        )
    xyz_axis_to_array_axis = {"x": 0, "y": 1, "z": 2}
    axes = [xyz_axis_to_array_axis[axis] for axis in convention]
    xyzw = jnp.roll(wxyz, shift=-1)
    angle_first, angle_third = (0, 2)
    i, j, k = axes
    eps = 1e-7
    symmetric = i == k
    if symmetric:
        k = 3 - i - j
        sign = -jnp.array((i - j) * (j - k) * (k - i) // 2, dtype=xyzw.dtype)
        a, b, c, d = (xyzw[3], -xyzw[i], -xyzw[j], -xyzw[k] * sign)
    else:
        sign = -jnp.array((i - j) * (j - k) * (k - i) // 2, dtype=xyzw.dtype)
        a, b, c, d = (
            xyzw[3] + xyzw[j],
            -xyzw[i] - xyzw[k] * sign,
            -xyzw[j] + xyzw[3],
            -xyzw[k] * sign + xyzw[i],
        )
    angles = jnp.empty(3, dtype=xyzw.dtype)
    angles = angles.at[1].set(2 * jnp.arctan2(jnp.hypot(c, d), jnp.hypot(a, b)))
    case = jnp.where(jnp.abs(angles[1] - jnp.pi) <= eps, 2, 0)
    case = jnp.where(jnp.abs(angles[1]) <= eps, 1, case)
    half_sum = jnp.arctan2(b, a)
    half_diff = jnp.arctan2(d, c)
    angles = angles.at[0].set(
        jnp.where(case == 1, 2 * half_sum, 2 * half_diff * -1)
    )  # any degenerate case
    angles = angles.at[angle_first].set(
        jnp.where(case == 0, half_sum - half_diff, angles[angle_first])
    )
    angles = angles.at[angle_third].set(
        jnp.where(case == 0, half_sum + half_diff, angles[angle_third])
    )
    if not symmetric:
        angles = angles.at[angle_third].set(angles[angle_third] * sign)
    angles = angles.at[1].set(jnp.where(symmetric, angles[1], angles[1] - jnp.pi / 2))
    angles = (angles + jnp.pi) % (2 * jnp.pi) - jnp.pi
    return jnp.rad2deg(angles)
