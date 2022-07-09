import numpy as np
import msgpack
import os.path
import time

from ursinaxball.game.common_values import (
    INPUT_UP,
    INPUT_DOWN,
    INPUT_RIGHT,
    INPUT_LEFT,
    INPUT_SHOOT,
)

# This is temporary, until we have a proper game recorder system
# In the meantime, we will use the same recording system than my JS version


def input_translate_js(actions: np.ndarray) -> int:
    result = 0

    if actions[0] == -1:
        result += INPUT_LEFT
    elif actions[0] == 1:
        result += INPUT_RIGHT

    if actions[1] == -1:
        result += INPUT_DOWN
    elif actions[1] == 1:
        result += INPUT_UP

    if actions[2]:
        result += INPUT_SHOOT

    return result


class GameActionRecorder:
    def __init__(self, game, folder_rec: str = ""):

        self.game = game
        self.folder_rec = folder_rec

        self.filename = ""
        self.recording = []
        self.player_info = []
        self.player_action = []
        self.options = []

    def generate_replay_name(self):
        """
        The replay name is generated by the following format:
        'HBR_<timestamp>_<score_red>-<score_blue>_<team_kickoff>.hbar'
        Time stamp is the current time in seconds since 01/01/1970.
        """
        file_name = f"HBR_{str(int(time.time()))}_{self.game.score.red}-{self.game.score.blue}_{self.options[0]}.hbar"
        return file_name

    def start(self):
        self.player_info = [
            [player.name, f"{player.id}", player.team] for player in self.game.players
        ]
        self.player_action = [[] for _ in self.game.players]
        self.options = [self.game.team_kickoff * 8]

    def step(self, actions: np.ndarray):
        for i, action in enumerate(actions):
            self.player_action[i].append(input_translate_js(action))

    def stop(self, save: bool = True):
        players_list = [
            [info, action] for info, action in zip(self.player_info, self.player_action)
        ]
        if len(self.options) > 0:
            self.recording = [self.options[0], players_list]
            self.filename = self.generate_replay_name()
            if save:
                self.save(self.filename)

        self.recording = []
        self.player_info = []
        self.player_action = []
        self.options = []

    def save(self, file_name: str) -> None:
        with open(os.path.join(os.path.curdir, self.folder_rec, file_name), "wb+") as f:
            encoded_recording = msgpack.packb(self.recording)
            f.write(encoded_recording)

    def read_from_file(self, file_name: str) -> None:
        with open(file_name, "rb") as f:
            self.recording = msgpack.unpackb(f.read())
            self.options = [self.recording[0]]
            self.player_info = [info for info, _ in self.recording[1]]
            self.player_action = [action for _, action in self.recording[1]]


class GamePositionRecorder:
    def __init__(self, game, folder_rec: str = ""):

        self.game = game
        self.folder_rec = folder_rec

        self.filename = ""
        self.recording = []
        self.player_info = []
        self.player_action = []
        self.options = []

    def generate_replay_name(self):
        """
        The replay name is generated by the following format:
        'HBR_<timestamp>_<score_red>-<score_blue>_<team_kickoff>.hbpr'
        Time stamp is the current time in seconds since 01/01/1970.
        """
        file_name = f"HBR_{str(int(time.time()))}_{self.game.score.red}-{self.game.score.blue}_{self.options[0]}.hbpr"
        return file_name

    def start(self):
        self.player_info = [
            [player.name, f"{player.id}", player.team] for player in self.game.players
        ]
        self.player_info.append(["ball", "0", 0])
        self.player_action = [[] for _ in self.game.players]
        self.player_action.append([])
        self.options = [self.game.team_kickoff * 8]

    def step(self, actions: np.ndarray):
        for i, player in enumerate(self.game.players):
            disc = player.disc
            disc_value = [
                disc.position[0],
                disc.position[1],
                disc.velocity[0],
                disc.velocity[1],
                int(player.kicking),
                int(player._kick_cancel),
            ]
            self.player_action[i].append(disc_value)
        ball = self.game.stadium_game.discs[0]
        ball_value = [
            ball.position[0],
            ball.position[1],
            ball.velocity[0],
            ball.velocity[1],
        ]
        self.player_action[-1].append(ball_value)

    def stop(self, save: bool = True):
        players_list = [
            [info, action] for info, action in zip(self.player_info, self.player_action)
        ]
        if len(self.options) > 0:
            self.recording = [self.options[0], players_list]
            self.filename = self.generate_replay_name()
            if save:
                self.save(self.filename)

        self.recording = []
        self.player_info = []
        self.player_action = []
        self.options = []

    def save(self, file_name: str) -> None:
        with open(os.path.join(os.path.curdir, self.folder_rec, file_name), "wb+") as f:
            encoded_recording = msgpack.packb(self.recording)
            f.write(encoded_recording)

    def read_from_file(self, file_name: str) -> None:
        with open(file_name, "rb") as f:
            self.recording = msgpack.unpackb(f.read())
            self.options = [self.recording[0]]
            self.player_info = [info for info, _ in self.recording[1]]
            self.player_action = [action for _, action in self.recording[1]]
