from __future__ import annotations

import copy
import logging
from collections.abc import Sequence
from typing import Optional, Union

import numpy as np
from numpy.typing import NDArray

from ursinaxball.common_values import CollisionFlag, GameState, TeamID
from ursinaxball.modules import (
    GameActionRecorder,
    GameRenderer,
    GameScore,
    PlayerHandler,
    resolve_collisions,
    update_discs,
)
from ursinaxball.modules.systems.game_config import GameConfig
from ursinaxball.objects.base import Disc
from ursinaxball.objects.stadium_object import Stadium, load_stadium_hbs

log = logging.getLogger(__name__)

# Type aliases for better type checking
ActionArray = NDArray[np.int_]
ActionType = Union[ActionArray, Sequence[int], Sequence[Optional[int]], None]
ActionsType = Union[NDArray[np.int_], Sequence[Optional[ActionType]]]

DEFAULT_ACTION = [0, 0, 0]


def normalize_action(action: ActionType) -> list[int]:
    """Convert any action type to a list of integers.

    Args:
        action: The action to normalize

    Returns:
        list[int]: A list of integers representing the normalized action
    """
    if action is None:
        return DEFAULT_ACTION.copy()

    try:
        if isinstance(action, np.ndarray):
            return [int(x) for x in action.tolist()]
        if isinstance(action, (list, tuple)):
            return [0 if x is None else int(x) for x in action]
        return DEFAULT_ACTION.copy()
    except (TypeError, ValueError):
        return DEFAULT_ACTION.copy()


class Game:
    def __init__(self, config: GameConfig | None = None, **kwargs):
        if config is None:
            config = GameConfig(**kwargs)

        self.config = config  # Store config for reference
        self.score = GameScore()
        self.state = GameState.KICKOFF
        self.players: list[PlayerHandler] = []
        self.team_kickoff = TeamID.RED
        self.stadium_file = config.stadium_file
        self.stadium_store: Stadium = load_stadium_hbs(self.stadium_file)
        self.stadium_game: Stadium = copy.deepcopy(self.stadium_store)
        self.enable_recorder = config.enable_recorder
        self.recorder: GameActionRecorder | None = (
            GameActionRecorder(self, config.folder_rec)
            if config.enable_recorder
            else None
        )
        self.enable_renderer = config.enable_renderer
        self.renderer: GameRenderer | None = (
            GameRenderer(self, config.enable_vsync, config.fov)
            if config.enable_renderer
            else None
        )

    def add_player(self, player: PlayerHandler) -> None:
        self.players.append(player)

    def add_players(self, players: list[PlayerHandler]) -> None:
        for player in players:
            self.add_player(player)

    def make_player_action(self, player: PlayerHandler, action: ActionType) -> None:
        player.action = normalize_action(action)
        player.resolve_movement(self.stadium_game, self.score)

    def get_player_by_id(self, player_id: int) -> PlayerHandler | None:
        for player in self.players:
            if player.id == player_id:
                return player
        return None

    def load_map(self, map_file: str) -> None:
        """
        Loads a map from a hbs file.
        """
        self.stadium_file = map_file
        self.stadium_store: Stadium = load_stadium_hbs(map_file)
        self.stadium_game: Stadium = copy.deepcopy(self.stadium_store)

    def check_goal(self, previous_discs_position: list[Disc]) -> int:
        current_disc_position = [
            disc
            for disc in self.stadium_game.discs
            if disc.collision_group & CollisionFlag.SCORE != 0
        ]
        for previous_disc_pos, current_disc_pos in zip(
            previous_discs_position, current_disc_position
        ):
            for goal in self.stadium_game.goals:
                previous_p0 = previous_disc_pos.position - goal.points[0]
                current_p0 = current_disc_pos.position - goal.points[0]
                current_p1 = current_disc_pos.position - goal.points[1]
                disc_vector = current_disc_pos.position - previous_disc_pos.position
                goal_vector = goal.points[1] - goal.points[0]
                if (
                    np.cross(current_p0, disc_vector)
                    * np.cross(current_p1, disc_vector)
                    <= 0
                    and np.cross(previous_p0, goal_vector)
                    * np.cross(current_p0, goal_vector)
                    <= 0
                ):
                    team_score = TeamID.RED if goal.team == "red" else TeamID.BLUE
                    return team_score

        return TeamID.SPECTATOR

    def _handle_kickoff_state(self) -> None:
        """Handle the KICKOFF state logic."""
        for player in self.players:
            if player.disc.position is not None:
                kickoff_collision = (
                    CollisionFlag.REDKO
                    if self.team_kickoff == TeamID.RED
                    else CollisionFlag.BLUEKO
                )
                player.disc.collision_mask = (
                    CollisionFlag.PLAYER_COLLISION | kickoff_collision
                )

        ball_disc = self.stadium_game.discs[0]
        if np.linalg.norm(ball_disc.velocity) > 0:
            log.debug("Kickoff made")
            self.state = GameState.PLAYING

    def _handle_playing_state(self, previous_discs_position: list[Disc]) -> None:
        """Handle the PLAYING state logic."""
        for player in self.players:
            if player.disc.position is not None:
                player.disc.collision_mask = CollisionFlag.PLAYER_COLLISION

        team_goal = self.check_goal(previous_discs_position)
        if team_goal != TeamID.SPECTATOR:
            team_goal_string = "Red" if team_goal == TeamID.RED else "Blue"
            log.debug(f"Team {team_goal_string} conceded a goal")
            self.state = GameState.GOAL
            self.score.update_score(team_goal)
            if not self.score.is_game_over():
                self.team_kickoff = (
                    TeamID.BLUE if team_goal == TeamID.BLUE else TeamID.RED
                )
        elif self.score.is_game_over():
            self.state = GameState.END
            self.score.end_animation()

    def _handle_goal_state(self) -> None:
        """Handle the GOAL state logic."""
        self.score.animation_timeout -= 1
        if not self.score.is_animation():
            if self.score.is_game_over():
                self.state = GameState.END
                self.score.end_animation()
            else:
                self.reset_discs_positions()
                self.state = GameState.KICKOFF

    def _handle_end_state(self) -> bool:
        """Handle the END state logic."""
        self.score.animation_timeout -= 1
        return not self.score.is_animation()

    def handle_game_state(self, previous_discs_position: list[Disc]) -> bool:
        """
        Handle the game state machine and transitions.

        Args:
            previous_discs_position: List of disc positions from previous step

        Returns:
            bool: True if game is done, False otherwise
        """
        self.score.step(self.state)

        if self.state == GameState.KICKOFF:
            self._handle_kickoff_state()
        elif self.state == GameState.PLAYING:
            self._handle_playing_state(previous_discs_position)
        elif self.state == GameState.GOAL:
            self._handle_goal_state()
        elif self.state == GameState.END:
            return self._handle_end_state()

        return False

    def reset_discs_positions(self) -> None:
        discs_game = (
            self.stadium_game.discs
            if self.stadium_game.kickoff_reset == "full"
            else [self.stadium_game.discs[0]]
        )
        discs_store = (
            self.stadium_store.discs
            if self.stadium_store.kickoff_reset == "full"
            else [self.stadium_store.discs[0]]
        )

        for disc_game, disc_store in zip(discs_game, discs_store):
            disc_game.copy(disc_store)

        red_count = 0
        blue_count = 0
        red_spawns = self.stadium_store.red_spawn_points
        blue_spawns = self.stadium_store.blue_spawn_points
        for player in self.players:
            player.disc.copy(self.stadium_store.player_physics)
            player.disc.collision_group |= (
                CollisionFlag.RED if player.team == TeamID.RED else CollisionFlag.BLUE
            )
            player.disc.player_id = player.id
            player.set_color()

            if player.team == TeamID.RED:
                if len(red_spawns) > 0:
                    index_red = min(red_count, len(red_spawns))
                    player.disc.position = np.array(red_spawns[index_red])
                else:
                    player.disc.position = np.array(
                        [
                            -self.stadium_game.spawn_distance,
                            -55 * (red_count + 1 >> 1)
                            if (red_count % 2) == 1
                            else 55 * (red_count + 1 >> 1),
                        ]
                    )
                red_count += 1

            elif player.team == TeamID.BLUE:
                if len(blue_spawns) > 0:
                    index_blue = min(blue_count, len(blue_spawns))
                    player.disc.position = np.array(blue_spawns[index_blue])
                else:
                    player.disc.position = np.array(
                        [
                            self.stadium_game.spawn_distance,
                            -55 * (blue_count + 1 >> 1)
                            if (blue_count % 2) == 1
                            else 55 * (blue_count + 1 >> 1),
                        ]
                    )
                blue_count += 1

    def start(self) -> None:
        for player in self.players:
            self.stadium_game.discs.append(player.disc)
        self.reset_discs_positions()
        if self.recorder is not None:
            self.recorder.start()
        if self.renderer is not None:
            self.renderer.start()

    def step(self, actions: ActionsType) -> bool:
        if isinstance(actions, (list, tuple)):
            # Convert sequence of actions to numpy array, handling None values
            actions_list = [normalize_action(action) for action in actions]
            actions = np.array(actions_list, dtype=np.int_)

        # At this point actions is guaranteed to be a numpy array
        for action, player in zip(actions, self.players):
            self.make_player_action(player, action)

        previous_discs_position = [
            copy.deepcopy(disc)
            for disc in self.stadium_game.discs
            if disc.collision_group & CollisionFlag.SCORE != 0
        ]
        update_discs(self.stadium_game, self.players)
        resolve_collisions(self.stadium_game)
        done = self.handle_game_state(previous_discs_position)
        if self.recorder is not None:
            self.recorder.step(actions)  # type: ignore
        if self.renderer is not None:
            self.renderer.update()

        return done

    def stop(self, save_recording: bool) -> None:
        if self.recorder is not None:
            self.recorder.stop(save=save_recording)
            if save_recording:
                log.debug(f"Recording saved under {self.recorder.filename}")

        log.debug(
            f"Game stopped with score {self.score.red}-{self.score.blue}"
            + f" at {round(self.score.time, 2)}s\n",
        )

        self.score.stop()
        self.state = GameState.KICKOFF
        self.team_kickoff = TeamID.RED
        self.stadium_game: Stadium = copy.deepcopy(self.stadium_store)
        if self.recorder is not None:
            self.recorder = GameActionRecorder(self, self.config.folder_rec)
        if self.renderer is not None:
            self.renderer.stop()

    def reset(self, save_recording: bool) -> None:
        self.stop(save_recording)
        self.start()


if __name__ == "__main__":
    from ursinaxball.modules.bots import ConstantActionBot

    game = Game()

    custom_score = GameScore(time_limit=1, score_limit=1)
    game.score = custom_score

    bot_1 = ConstantActionBot([1, 0, 0])
    bot_2 = ConstantActionBot([1, 1, 1], symmetry=True)

    player_red = PlayerHandler("P0", TeamID.RED, bot=bot_1)
    player_blue = PlayerHandler("P1", TeamID.BLUE, bot=bot_2)
    game.add_players([player_red, player_blue])

    game.start()

    done = False
    while not done:
        actions_player_1 = player_red.step(game)
        actions_player_2 = player_blue.step(game)
        done = game.step([actions_player_1, actions_player_2])

    game.stop(save_recording=False)
