from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import numpy as np

from ursinaxball.objects.base.disc import Disc, DiscRaw
from ursinaxball.utils.enums import CollisionFlag

if TYPE_CHECKING:
    from ursinaxball.objects.base.trait import Trait

Ball = Disc


def get_ball(
    ball: str | dict | None,
    discs: list[Disc],
    traits: dict[str, Trait],
):
    ball_default = Ball(
        position=np.array([0.0, 0.0]),
        speed=np.array([0.0, 0.0]),
        gravity=np.array([0.0, 0.0]),
        radius=10.0,
        inv_mass=1.0,
        damping=0.99,
        b_coef=0.5,
        color=(255, 255, 255, 255),
        c_group=CollisionFlag.from_list(["ball"]),
        c_mask=CollisionFlag.from_list(["all"]),
    )

    if ball is None:
        return ball_default

    if isinstance(ball, str):
        if ball == "disc0":
            disc = discs.pop(0)
            return Ball(**disc.__dict__)
        else:
            raise ValueError(f"Invalid ball value: {ball}")

    if isinstance(ball, dict):
        ball["pos"] = [0.0, 0.0]
        disc_raw = msgspec.convert(ball, DiscRaw)
        disc = disc_raw.to_disc(traits)
        disc.c_group |= CollisionFlag.KICK | CollisionFlag.SCORE

        ball_dict_tuple = disc.__rich_repr__()
        ball_dict = dict(ball_dict_tuple)
        return Ball(**ball_dict)