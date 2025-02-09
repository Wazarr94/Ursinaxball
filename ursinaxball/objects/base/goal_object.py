from __future__ import annotations

import numpy as np

from ursinaxball.objects.base.physics_object import PhysicsObject


class Goal(PhysicsObject):
    """
    A class to represent the state of a goal from the game.
    """

    def __init__(self, data_object: dict | None, data_stadium: dict):
        if data_object is None:
            data_object = {}

        self.points: list[np.ndarray] = np.array(
            [data_object.get("p0"), data_object.get("p1")]
        )
        self.team = data_object.get("team")
        self.trait = data_object.get("trait")

        self.apply_trait(self, data_stadium)

    def apply_default_values(self):
        """
        Applies the default values to the goal if they are none
        """
