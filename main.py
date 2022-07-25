from __future__ import annotations
from typing import Any, Sequence, Union

import pygame

import math
import time
import json
import random
import copy


class ToggleKey:
    def __init__(self, default: bool = False):
        self.was_down = default

    def down(self, condition: bool) -> bool:
        if not self.was_down and condition:
            self.was_down = True
            return True
        elif not condition:
            self.was_down = False
        return False


class KeyList:
    def __init__(self, keys: list[int]):
        self.keys = keys

    def down(self, keys_down: Sequence[bool]) -> bool:
        for key in self.keys:
            if keys_down[key]:
                return True
        return False


class Interval:
    def __init__(self, period: float, last: float = 1 / 500):
        self.period = period
        self.last = last

    def update(self, ticks: float) -> bool:
        if self.last + self.period < ticks:
            self.last += self.period
            return True
        return False

    def reset(self, last: float = 1 / 500):
        self.last = last


class RandomInterval(Interval):
    def __init__(self, base_period: float, variance: float, last: float = 1 / 500):
        super().__init__(-1, last)  # the -1 is set with the randomize()
        self.base_period = base_period
        self.variance = variance
        self.randomize()

    def randomize(self) -> None:
        self.period = self.base_period + random.uniform(-self.variance, +self.variance)

    def update(self, ticks: float) -> bool:
        if super().update(ticks):
            self.randomize()
            return True
        return False


class Vector:
    def __init__(self, x: float, y: float):
        self.x: float = x
        self.y: float = y

    def __str__(self) -> str:
        return "<%f, %f>" % (self.x, self.y)

    def set_vec(self, vec: Vector) -> None:
        self.x = vec.x
        self.y = vec.y

    def get_int(self) -> Vector:
        return Vector(int(self.x), int(self.y))

    def get_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    def get_int_tuple(self) -> tuple[int, int]:
        return (int(self.x), int(self.y))

    def get_angle(self) -> float:
        try:
            angle = math.atan(self.y / self.x) * 180 / math.pi
            if self.x < 0:
                angle += 180
        except ZeroDivisionError:
            angle = 90 if self.y > 0 else 270
        return angle % 360

    def set_angle(self, angle: float) -> None:
        current_length = self.calc_length()
        self.x = math.cos(angle * math.pi / 180)
        self.y = math.sin(angle * math.pi / 180)
        self.set_vec(self.scale(current_length))

    def calc_length(self) -> float:
        return math.sqrt(self.x**2 + self.y**2)

    def calc_dist_to(self, vec: Vector) -> float:
        return self.subtract(vec).calc_length()

    def add(self, vec: Vector) -> Vector:
        return Vector(self.x + vec.x, self.y + vec.y)

    def subtract(self, vec: Vector) -> Vector:
        return self.add(vec.scalar(-1))

    def apply(self, vec: Vector) -> None:
        self.set_vec(self.add(vec))

    def scalar(self, s: float) -> Vector:
        return Vector(self.x * s, self.y * s)

    def scale(self, length: float) -> Vector:
        current_length = self.calc_length()
        if current_length == 0:
            return Vector(0, 0)
        return self.scalar(length / current_length)

    def get_map_tup(self, tile_size: int) -> tuple[int, int]:
        return (int(self.x / tile_size), int(self.y / tile_size))

    def get_map_str(self, tile_size: int) -> str:
        return str(int(self.x / tile_size)) + ";" + str(int(self.y / tile_size))


class Hitbox:
    def __init__(self, pt: Vector, w: float, h: float, color: str):
        self.pt: Vector = pt
        self.w: float = w
        self.h: float = h
        self.color: str = color

    def __str__(self) -> str:
        return "(%s, %f, %f)" % (self.pt, self.w, self.h)

    def get_center(self) -> Vector:
        return Vector(self.pt.x + self.w / 2, self.pt.y + self.h / 2)

    def get_rect(self) -> pygame.Rect:
        return pygame.Rect(self.pt.x, self.pt.y, self.w, self.h)

    def collide(self, hb: Hitbox) -> bool:
        return (
            self.pt.x < hb.pt.x + hb.w
            and hb.pt.x < self.pt.x + self.w
            and self.pt.y < hb.pt.y + hb.h
            and hb.pt.y < self.pt.y + self.h
        )

    def update(self, state: State) -> None:
        pass

    def draw(self, win: pygame.surface.Surface) -> None:
        pygame.draw.rect(win, self.color, self.get_rect())


class Chest(Hitbox):
    def __init__(self, chest_options, bot_tile: Tile):
        super().__init__(
            Vector(
                bot_tile.pt.x + (bot_tile.w - chest_options["w"]) / 2,
                bot_tile.pt.y - chest_options["h"],
            ),
            chest_options["w"],
            chest_options["h"],
            chest_options["color"],
        )
        self.bot_tile = bot_tile

    def update(self, state: State) -> None:
        self.pt.y = self.bot_tile.pt.y - self.h

        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_ys = [map_tup[1] - 1, map_tup[1]]
        for y in map_ys:
            map_str = str(map_tup[0]) + ";" + str(y)
            try:
                for tile in state.tile_map[map_str]:
                    collision = tile.directional_collide(self)
                    if collision == "bottom":
                        state.chests.remove(self)  # TODO: remove in iteration?
                        return
            except KeyError:
                pass

        if (
            state.player.can_interact() and self.collide(state.player)
        ) or not self.bot_tile in state.tiles:
            self.pop(state)

    def pop(self, state: State) -> None:
        if self in state.chests:
            state.chests.remove(self)  # TODO: remove in iteration?
            num_coins = random.choice(state.options["coin"]["pop"]["coin_chances"])
            for _ in range(num_coins):
                c = Coin(
                    self.get_center(),
                    state.options["coin"],
                    Vector(
                        random.uniform(
                            -state.options["coin"]["pop"]["speed"],
                            state.options["coin"]["pop"]["speed"],
                        ),
                        -state.options["coin"]["pop"]["vel"],
                    ).scale(state.options["coin"]["pop"]["vel"]),
                    state.options["coin"]["pop"]["gravity"],
                )
                state.coins.append(c)


class Movable(Hitbox):
    def __init__(
        self, pt: Vector, w: float, h: float, color: str, move_vec: Vector, gravity: float
    ):
        super().__init__(pt, w, h, color)
        self.move_vec: Vector = move_vec
        self.gravity: float = gravity

    def move(self, delta: float) -> None:
        self.move_vec.y += self.gravity * delta
        self.pt.apply(self.move_vec.scalar(delta))

    def scroll(self, dist: float):
        self.pt.y += dist


class Effect(Movable):
    def __init__(
        self,
        pt: Vector,
        w: float,
        h: float,
        color: str,
        move_vec: Vector,
        gravity: float,
        duration: float,
    ):
        super().__init__(pt, w, h, color, move_vec, gravity)
        self.duration: float = duration
        self.base_duration: float = duration

    def update(self, state: State) -> None:
        self.move(state.delta)
        self.duration -= state.delta
        if self.duration <= 0:
            state.effects.remove(self)  # TODO: remove in iteration?


class CircleEffect(Effect):
    # Note: w = h which are both r
    def __init__(
        self, pt: Vector, r: float, color: str, move_vec: Vector, gravity: float, duration: float
    ):
        super().__init__(pt, r, r, color, move_vec, gravity, duration)
        self.base_r = r
        self.log_rate = -self.base_r / math.log(duration + 1, 10)

    def update(self, state: State) -> None:
        super().update(state)
        self.w = self.log_rate * math.log(self.base_duration - self.duration + 1, 10) + self.base_r

    def draw(self, win: pygame.surface.Surface) -> None:
        pygame.draw.circle(win, self.color, self.pt.get_tuple(), self.w)


class Player(Movable):
    def __init__(self, options: dict[str, Any]):
        super().__init__(
            Vector(
                (options["window"]["width"] - options["player"]["w"]) / 2,
                (options["window"]["height"] - options["player"]["h"]) / 2,
            ),
            options["player"]["w"],
            options["player"]["h"],
            options["player"]["alive_color"],
            Vector(0, 0),
            options["player"]["gravity"],
        )
        self.speed: float = options["player"]["speed"]
        self.jump_vel: float = options["player"]["jump_vel"]
        self.jumps: int = 1

        self.powers: dict[str, Any] = options["player"]["powers"]
        self.power_cd: float = 0
        self.shield: float = 0

        self.lives: int = 1
        self.respawn: float = 0
        self.status: str = "alive"
        self.flicker: Interval = Interval(0.1, self.respawn)
        self.show: bool = True

        self.space_tk: ToggleKey = ToggleKey(True)

    def key_input(self, keys_down: Sequence[bool], keys: dict[str, KeyList], power: str) -> None:
        self.move_vec.x = 0
        if keys["right"].down(keys_down):
            self.move_vec.x = self.speed
        elif keys["left"].down(keys_down):
            self.move_vec.x = -self.speed
        jump_limit = self.powers["triple_jump"]["jumps"] if power == "triple_jump" else 2
        if self.jumps < jump_limit and self.space_tk.down(keys["up"].down(keys_down)):
            self.move_vec.y = -self.jump_vel
            self.jumps += 1
        elif keys["down"].down(keys_down):
            if power == "downthrust" and self.power_cd >= self.powers["downthrust"]["cd"]:
                self.move_vec.y += self.powers["downthrust"]["vel"]
                self.power_cd = 0
            elif power == "shield" and self.power_cd >= self.powers["shield"]["cd"]:
                self.shield = self.powers["shield"]["time"]
                self.power_cd = 0

    def check_tile_collision(self, state: State) -> None:
        current_self: Player = copy.deepcopy(self)  # TODO: not sure if the copy is needed

        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_xs = [map_tup[0], map_tup[0] + 1]
        map_ys = [map_tup[1] - 1, map_tup[1], map_tup[1] + 1]
        for x in map_xs:
            for y in map_ys:
                map_str = str(x) + ";" + str(y)
                try:
                    for tile in state.tile_map[map_str]:
                        collision = tile.directional_collide(current_self)
                        if collision == "bottom":
                            if self.shield > 0:
                                self.shield = 0
                                state.tiles.remove(tile)
                            else:
                                self.trigger_respawn(state)
                        elif collision == "top":
                            self.pt.y = tile.pt.y - self.h
                            self.move_vec.y = 0
                            self.jumps = 0
                            self.space_tk.down(False)
                        elif collision == "left":
                            self.pt.x = tile.pt.x - self.w
                        elif collision == "right":
                            self.pt.x = tile.pt.x + tile.w
                except KeyError:
                    pass

    def can_interact(self) -> bool:
        return self.lives >= 1 and not (self.status == "dead" or self.status == "true_death")

    def trigger_respawn(self, state: State) -> None:
        if self.status == "alive":
            self.lives -= 1
            if self.lives >= 1 and self.status == "alive":  # TODO
                self.status = "dead"
                self.respawn = -state.options["player"]["respawn_delay"]
            elif self.lives <= 0:
                self.status = "true_death"

    def update(self, state: State) -> None:
        if self.can_interact():
            self.key_input(state.keys_down, state.keys, state.save["power"])
            self.shield -= state.delta
            if state.active_power_type():
                self.power_cd += state.delta
                self.power_cd = min(self.power_cd, self.powers[state.save["power"]]["cd"])

            if self.pt.x < state.options["tile"]["w"]:
                self.pt.x = state.options["tile"]["w"]
            elif self.pt.x + self.w + state.options["tile"]["w"] > state.options["window"]["width"]:
                self.pt.x = state.options["window"]["width"] - self.w - state.options["tile"]["w"]

            self.move(state.delta)
            self.check_tile_collision(state)
        elif self.status == "true_death":
            self.color = self.color = state.options["player"]["dead_color"]
        elif self.status == "dead":
            self.respawn += state.delta
            self.color = state.options["player"]["respawn_color"]
            if self.respawn >= 0:
                self.flicker.reset(self.respawn)
                self.status = "respawning"
                self.destory_nearby(state)
                self.color = state.options["player"]["alive_color"]
        if self.status == "respawning":
            self.respawn += state.delta
            if self.flicker.update(self.respawn):
                self.show = not self.show
            if self.respawn >= state.options["player"]["respawn_time"]:
                self.color = state.options["player"]["alive_color"]
                self.status = "alive"

    def destory_nearby(self, state: State):
        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_xs = [map_tup[0] - 2, map_tup[0] - 1, map_tup[0], map_tup[0] + 1, map_tup[0] + 2]
        map_ys = [map_tup[1] - 2, map_tup[1] - 1, map_tup[1], map_tup[1] + 1, map_tup[1] + 2]
        for x in map_xs:
            for y in map_ys:
                map_str = str(x) + ";" + str(y)
                try:
                    for i in range(len(state.tile_map[map_str]) - 1, -1, -1):
                        if type(state.tile_map[map_str][i]) != EdgeTile and circle_rect_collide(
                            state.tile_map[map_str][i],
                            self.get_center(),
                            state.options["player"]["respawn_r"],
                        ):
                            state.tiles.remove(state.tile_map[map_str][i])
                        pass
                except KeyError:
                    pass

        for chest in state.chests:
            if circle_rect_collide(chest, self.get_center(), state.options["player"]["respawn_r"]):
                chest.pop(state)

        state.effects.append(
            CircleEffect(
                self.get_center(),
                state.options["player"]["respawn_r"],
                state.options["player"]["respawn_color"],
                Vector(0, 0),
                0,
                state.options["tile"]["heavy"]["draw_time"],
            )
        )

    def draw(self, win: pygame.surface.Surface) -> None:
        if not (self.status == "respawning" and not self.show):
            super().draw(win)
            if self.shield > 0:
                pygame.draw.rect(win, self.powers["shield"]["color"], self.get_rect(), 5)


class Tile(Movable):
    def __init__(
        self,
        pt: Vector,
        tile_options: dict[str, Any],
        color: str,
    ):
        super().__init__(
            pt,
            tile_options["w"],
            tile_options["w"],
            color,
            Vector(0, tile_options["fall_speed"]),
            0,
        )
        self.hbs_size: float = tile_options["hbs_size"]
        self.hbs_len: float = self.w - 2 * tile_options["hbs_size"]
        self.side_hbs: dict[str, Hitbox] = {
            "top": Hitbox(Vector(-1, -1), self.hbs_len, self.hbs_size, tile_options["hbs_color"]),
            "bottom": Hitbox(
                Vector(-1, -1), self.hbs_len, self.hbs_size, tile_options["hbs_color"]
            ),
            "left": Hitbox(Vector(-1, -1), self.hbs_size, self.hbs_len, tile_options["hbs_color"]),
            "right": Hitbox(Vector(-1, -1), self.hbs_size, self.hbs_len, tile_options["hbs_color"]),
        }
        self.update_side_hbs()

    def update_side_hbs(self) -> None:
        # TODO: is it slow to always recreate the Vectors?
        self.side_hbs["top"].pt = Vector(self.pt.x + self.hbs_size, self.pt.y)
        self.side_hbs["bottom"].pt = Vector(
            self.pt.x + self.hbs_size, self.pt.y + self.h - self.hbs_size
        )
        self.side_hbs["left"].pt = Vector(self.pt.x, self.pt.y + self.hbs_size)
        self.side_hbs["right"].pt = Vector(
            self.pt.x + self.w - self.hbs_size, self.pt.y + self.hbs_size
        )

    def update(self, state: State) -> None:
        self.move(
            state.delta
            * (
                state.player.powers["tile_fall"]["decrease"]
                if state.save["power"] == "tile_fall"
                else 1
            )
        )
        self.land(state)

    def land(self, state: State) -> None:
        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_ys = [map_tup[1], map_tup[1] + 1]
        for y in map_ys:
            map_str = str(map_tup[0]) + ";" + str(y)
            try:
                for tile in state.tile_map[map_str]:
                    if tile != self and self.collide(tile):
                        self.pt.y = tile.pt.y - self.h
                        self.update_side_hbs()
                        return
            except KeyError:
                pass

    def move(self, delta: float) -> None:
        super().move(delta)
        self.update_side_hbs()

    def scroll(self, dist: float) -> None:
        super().scroll(dist)
        self.update_side_hbs()

    def directional_collide(self, hb: Hitbox) -> str:
        if self.collide(hb):
            if hb.collide(self.side_hbs["top"]):
                return "top"
            elif hb.collide(self.side_hbs["bottom"]):
                return "bottom"
            elif hb.collide(self.side_hbs["left"]):
                return "left"
            elif hb.collide(self.side_hbs["right"]):
                return "right"
            return "center"
        return "none"

    def draw(self, win: pygame.surface.Surface) -> None:
        super().draw(win)
        for value in self.side_hbs.values():
            value.draw(win)


class EdgeTile(Tile):
    def __init__(self, pt: Vector, tile_options: dict[str, Any], color: str):
        super().__init__(pt, tile_options, color)
        self.move_vec.y = 0


class HeavyTile(Tile):
    def __init__(self, pt: Vector, tile_options: dict[str, Any]):
        super().__init__(pt, tile_options, tile_options["heavy"]["color"])
        self.move_vec.y *= tile_options["heavy"]["fall"]

    def check_explosion_tiles(self, state: State) -> None:
        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_xs = [map_tup[0] - 2, map_tup[0] - 1, map_tup[0], map_tup[0] + 1, map_tup[0] + 2]
        map_ys = [map_tup[1] - 2, map_tup[1] - 1, map_tup[1], map_tup[1] + 1, map_tup[1] + 2]
        for x in map_xs:
            for y in map_ys:
                map_str = str(x) + ";" + str(y)
                try:
                    for i in range(len(state.tile_map[map_str]) - 1, -1, -1):
                        if type(state.tile_map[map_str][i]) != EdgeTile and circle_rect_collide(
                            state.tile_map[map_str][i],
                            self.get_center(),
                            state.options["tile"]["heavy"]["r"],
                        ):
                            state.tiles.remove(state.tile_map[map_str][i])
                        pass
                except KeyError:
                    pass

    def land(self, state: State) -> None:
        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_ys = [map_tup[1], map_tup[1] + 1]
        for y in map_ys:
            map_str = str(map_tup[0]) + ";" + str(y)
            try:
                for tile in state.tile_map[map_str]:
                    if tile != self and self.collide(tile):
                        self.check_explosion_tiles(state)

                        if circle_rect_collide(
                            state.player, self.get_center(), state.options["tile"]["heavy"]["r"]
                        ):
                            if state.player.shield > 0:
                                state.player.shield = 0
                            else:
                                state.player.trigger_respawn(state)

                        for chest in state.chests:
                            if circle_rect_collide(
                                chest, self.get_center(), state.options["player"]["respawn_r"]
                            ):
                                chest.pop(state)

                        state.effects.append(
                            CircleEffect(
                                self.get_center(),
                                state.options["tile"]["heavy"]["r"],
                                state.options["tile"]["heavy"]["explosion_color"],
                                Vector(0, 0),
                                0,
                                state.options["tile"]["heavy"]["draw_time"],
                            )
                        )
                        return
            except KeyError:
                pass


class Coin(Movable):
    def __init__(
        self,
        pt: Vector,
        coin_options: dict[str, Any],
        move_vec: Vector = None,
        gravity: float = None,
    ):
        if move_vec is None or gravity is None:
            super().__init__(
                pt,
                coin_options["w"],
                coin_options["h"],
                coin_options["color"],
                Vector(0, coin_options["fall_speed"]),
                0,
            )
        else:
            super().__init__(
                pt,
                coin_options["w"],
                coin_options["h"],
                coin_options["color"],
                move_vec,
                gravity,
            )

    def update(self, state: State):
        self.move(state.delta)

        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_xs = [map_tup[0], map_tup[0] + 1]
        map_ys = [map_tup[1] - 1, map_tup[1], map_tup[1] + 1]
        for x in map_xs:
            for y in map_ys:
                map_str = str(x) + ";" + str(y)
                try:
                    for tile in state.tile_map[map_str]:
                        collision = tile.directional_collide(self)
                        if collision == "bottom":
                            state.coins.remove(self)  # TODO: remove in iteration?
                            return  # avoid double-removal chance
                        elif collision == "top":
                            self.pt.y = tile.pt.y - self.h
                            self.move_vec.x -= (
                                state.options["coin"]["pop"]["friction"]
                                * state.delta
                                * get_sign(self.move_vec.x)
                            )
                            if self.gravity != 0:
                                self.move_vec.y = 0
                        elif collision == "left":
                            self.pt.x = tile.pt.x - self.w
                            self.move_vec.x = 0
                        elif collision == "right":
                            self.pt.x = tile.pt.x + tile.w
                            self.move_vec.x = 0
                except KeyError:
                    pass

        if state.player.can_interact() >= 1 and self.move_vec.y >= 0 and self.collide(state.player):
            state.coins.remove(self)  # TODO: remove in iteration?
            state.score += 1  # TODO: make 1
            if state.score // state.options["game"]["score_per_Life"] > state.lives_given:
                state.lives_given += 1
                state.player.lives += 1


class State:
    def __init__(self, options: dict[str, Any], save: dict[str, Any]):
        self.options: dict[str, Any] = options
        self.save = save
        self.paused: bool = False
        self.screen: str = "intro"
        self.keys_down: Sequence[bool] = pygame.key.get_pressed()
        self.keys: dict[str, KeyList] = {
            "up": KeyList([pygame.K_SPACE, pygame.K_UP, pygame.K_w]),
            "down": KeyList([pygame.K_s, pygame.K_DOWN, pygame.K_LCTRL]),
            "left": KeyList([pygame.K_a, pygame.K_LEFT]),
            "right": KeyList([pygame.K_d, pygame.K_RIGHT]),
        }
        self.player: Player = Player(self.options)
        self.tiles: list[Tile] = []
        self.setup_tiles()
        self.tile_map: dict[str, list[Tile]] = {}
        self.coins: list[Coin] = []
        self.chests: list[Chest] = []
        self.effects: list[Effect] = []
        self.delta: float = 1 / 500
        self.ticks: float = 1 / 500
        self.score: int = -1
        self.lives_given: int = 0
        self.scrolling: float = 0
        self.full_rows: int = 3
        self.display_rows: int = 3
        self.tile_spawn: Interval = Interval(
            self.options["tile"]["spawn_interval_base"], self.ticks
        )
        self.tile_spawn_log_rate: float = (
            self.options["tile"]["spawn_interval_min"] - self.options["tile"]["spawn_interval_base"]
        ) / math.log(self.options["tile"]["spawn_interval_time"] + 1, 10)
        self.coin_spawn: RandomInterval = RandomInterval(
            self.options["coin"]["spawn_interval_base"],
            self.options["coin"]["spawn_interval_variance"],
            self.ticks,
        )
        self.fps_draw: Interval = Interval(self.options["game"]["fps"]["refresh"], self.ticks)
        self.display_fps: int = 500
        self.esc_tk: ToggleKey = ToggleKey()
        self.left_tk: ToggleKey = ToggleKey()
        self.right_tk: ToggleKey = ToggleKey()
        self.playing: bool = True
        self.updated_highscore: bool = False
        self.passive_highlight: float = 0
        self.powers: list[str] = list(self.options["player"]["powers"].keys())
        self.power_choice: int = self.powers.index(self.save["power"])

    def reset(self):
        self.player = Player(self.options)
        self.setup_tiles()
        self.coins = []
        self.chests = []
        self.effects = []
        self.ticks = 1 / 500
        self.scrolling = 0
        self.full_rows = 3
        self.display_rows = 3
        self.paused = False
        self.tile_spawn.reset(self.ticks)
        self.coin_spawn.reset(self.ticks)
        self.fps_draw.reset(self.ticks)
        self.score = 0
        self.updated_highscore = False

    def setup_tiles(self) -> None:
        self.tiles = []

        tile_y = self.options["tile"]["base_y"]
        tile_types = [Tile, Tile, EdgeTile]
        for i in range(1, self.options["tile"]["columns"] - 1):
            for j in range(len(tile_types)):
                self.tiles.append(
                    tile_types[j](
                        Vector(
                            i * self.options["tile"]["w"], tile_y + j * self.options["tile"]["w"]
                        ),
                        self.options["tile"],
                        self.options["tile"]["edge_color"]
                        if tile_types[j] == EdgeTile
                        else self.options["tile"]["color"],
                    )
                )

        tile_y += (len(tile_types) - 1) * self.options["tile"]["w"]
        while tile_y > -self.options["tile"]["w"]:
            self.tiles.append(
                EdgeTile(
                    Vector(0, tile_y), self.options["tile"], self.options["tile"]["edge_color"]
                )
            )
            self.tiles.append(
                EdgeTile(
                    Vector(self.options["window"]["width"] - self.options["tile"]["w"], tile_y),
                    self.options["tile"],
                    self.options["tile"]["edge_color"],
                )
            )
            tile_y -= self.options["tile"]["w"]
            self.options["tile"]["top_y"] = tile_y  # TODO: change - modifying self.options

    def exit(self) -> None:
        pygame.quit()
        self.playing = False

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.exit()

        if self.screen == "intro":
            if self.keys_down[pygame.K_ESCAPE]:
                self.exit()
            elif self.keys_down[pygame.K_RETURN]:
                self.after_intro()
        elif self.screen == "welcome":
            if self.keys["up"].down(self.keys_down):
                self.reset()
                self.screen = "game"
            elif self.keys_down[pygame.K_i]:
                self.screen = "instructions"
            elif self.keys_down[pygame.K_p]:
                self.screen = "powers"
            elif self.keys_down[pygame.K_ESCAPE]:
                self.exit()
        elif self.screen == "instructions":
            if self.keys_down[pygame.K_b]:
                self.screen = "welcome"
        elif self.screen == "powers":
            if self.keys_down[pygame.K_b]:
                self.screen = "welcome"
            elif (
                self.keys_down[pygame.K_RETURN]
                and self.powers[self.power_choice] in self.save["unlocked"]
            ):
                self.screen = "welcome"
                self.save["power"] = self.powers[self.power_choice]
                write_json(self.options["save_file"], self.save)
        elif self.screen == "game":
            if self.esc_tk.down(self.keys_down[pygame.K_ESCAPE]):
                self.paused = not self.paused
            elif (self.player.lives <= 0 and self.keys_down[pygame.K_r]) or (
                self.paused and self.keys_down[pygame.K_q]
            ):
                if not self.updated_highscore:
                    self.update_save()
                self.screen = "welcome"

    def draw(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]):
        win.fill(self.options["colors"]["background"])

        if self.screen == "intro":
            self.draw_intro(win, fonts)
        elif self.screen == "welcome":
            self.draw_welcome(win, fonts)
        elif self.screen == "instructions":
            self.draw_instructions(win, fonts)
        elif self.screen == "powers":
            self.draw_powers(win, fonts)
        elif self.screen == "game":
            self.draw_game(win, fonts)

        pygame.display.update()

    def update_save(self):
        if self.score > self.save["high_score"]:
            self.save["high_score"] = self.score
        self.save["gold"] += self.score
        write_json(self.options["save_file"], self.save)
        self.updated_highscore = True

    def next_frame(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]):
        if self.screen == "game":
            if not self.paused:
                self.update_game()
                self.update_passive_highlight()
            if self.player.lives <= 0 and not self.updated_highscore:
                self.update_save()
        self.draw(win, fonts)

    def run(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]):
        last_time = time.time()
        while self.playing:
            self.delta = time.time() - last_time
            if self.delta <= 0:
                self.delta = 1 / 500
            last_time = time.time()

            self.keys_down = pygame.key.get_pressed()  # TODO: ?? why this errors???

            self.next_frame(win, fonts)
            self.handle_events()

    def draw_game(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        self.draw_entities(win)
        self.draw_hud(win, fonts)

        if self.paused:
            self.draw_pause(win, fonts)
        elif self.player.lives <= 0:
            self.draw_death(win, fonts)

    def draw_entities(self, win: pygame.surface.Surface) -> None:
        entities: list[Hitbox] = self.tiles + self.chests + self.coins + self.effects + [self.player]  # type: ignore
        for e in entities:
            if e.pt.y < win.get_height() and e.pt.y > -e.h:
                e.draw(win)

    def create_tile_map(self) -> None:
        self.tile_map = {}
        for tile in self.tiles:
            map_str = tile.pt.get_map_str(self.options["tile"]["w"])
            try:
                self.tile_map[map_str].append(tile)
            except KeyError:
                self.tile_map[map_str] = [tile]

    def find_top_tiles(self) -> list[float]:
        top_tiles: list[float] = []
        for _ in self.options["tile"]["spawn_xs"]:
            top_tiles.append(self.options["tile"]["base_y"] - self.options["tile"]["w"])
        for tile in self.tiles:  # TODO!
            if type(tile) != EdgeTile:
                idx = self.options["tile"]["spawn_xs"].index(tile.pt.x)
                if top_tiles[idx] > tile.pt.y:
                    top_tiles[idx] = tile.pt.y
        return top_tiles

    def calc_drop_chances(self, top_tiles: list[float]) -> list[int]:
        max_value: float = max(top_tiles)
        min_value: float = min(top_tiles)

        old_range = max_value - min_value
        new_range = (
            self.options["tile"]["spawn_scale_max"] - self.options["tile"]["spawn_scale_min"]
        )

        drop_chances: list[int] = []
        for y in top_tiles:
            if y < 0:
                chance = 0
            else:
                try:
                    chance = ((y - min_value) * new_range) / old_range
                except ZeroDivisionError:
                    chance = 0
                chance += self.options["tile"]["spawn_scale_min"]
            drop_chances.append(int(chance))

        return drop_chances

    def count_full_rows(self) -> tuple[int, list[Tile], list[Tile]]:
        tile_ys: dict[float, int] = {}
        for tile in self.tiles:  # TODO!
            try:
                tile_ys[tile.pt.y] += 1
            except KeyError:
                tile_ys[tile.pt.y] = 1

        count = 0
        for value in tile_ys.values():
            if value == self.options["tile"]["columns"]:
                count += 1

        tiles_to_remove: list[Tile] = []
        below_tiles: list[Tile] = []

        sorted_keys = sorted(tile_ys.keys(), reverse=True)
        sorted_keys = [
            key for key in sorted_keys if tile_ys[key] == self.options["tile"]["columns"]
        ]

        if count > self.options["tile"]["row_limit"]:
            third_row_y = sorted_keys[2]
            for tile in self.tiles:  # TODO!
                if tile.pt.y == third_row_y:
                    tiles_to_remove.append(tile)
                elif tile.pt.y > third_row_y:
                    below_tiles.append(tile)
        elif count < self.options["tile"]["row_min"]:
            first_row_y = sorted_keys[0]
            for tile in self.tiles:  # TODO!
                if tile.pt.y == first_row_y:
                    below_tiles.append(tile)

        return count, tiles_to_remove, below_tiles

    def pick_lowest_x_idx(self) -> int:
        top_tiles = self.find_top_tiles()
        max_y = max(top_tiles)
        lowest_idxs: list[int] = []
        for i in range(len(top_tiles)):
            if top_tiles[i] == max_y:
                lowest_idxs.append(i)
        print(lowest_idxs, top_tiles)  # TODO
        return random.choice(lowest_idxs)

    def drop_tetris_tiles(self) -> Tile:
        main_idx = self.pick_lowest_x_idx()
        main_x = self.options["tile"]["spawn_xs"][main_idx]

        new_tile = None
        shape = random.choice(list(self.options["tile"]["tetris"]["shapes"].keys())).strip()
        chest_idx = random.choice(self.options["tile"]["tetris"]["shapes"][shape]["chest_tiles"])

        offset = 0
        if (
            main_idx == 0
            and "l" in self.options["tile"]["tetris"]["shapes"][shape]["offset_needed"]
        ):
            offset += 1
        elif (
            main_idx == len(self.options["tile"]["spawn_xs"]) - 1
            and "r" in self.options["tile"]["tetris"]["shapes"][shape]["offset_needed"]
        ):
            offset -= 1

        for key, item in self.options["tile"]["tetris"]["shapes"][shape]["tile_info"].items():
            tile = Tile(
                Vector(
                    main_x + (item[0] + (offset * item[2])) * self.options["tile"]["w"],
                    self.options["tile"]["spawn_y"] + item[1] * self.options["tile"]["w"],
                ),
                self.options["tile"],
                self.options["tile"]["color"],
            )
            if key == chest_idx:
                new_tile = tile
            else:
                self.tiles.append(tile)

        if not new_tile:
            new_tile = Tile(Vector(-1, -1), self.options["tile"], "#ffffff")
        return new_tile

    def update_game(self) -> None:
        self.create_tile_map()
        # Prob some way to do this without the '# type: ignore'
        entities: list[Hitbox] = self.tiles + self.chests + self.coins + self.effects + [self.player]  # type: ignore
        for e in entities:
            e.update(self)

        count, tiles_to_remove, below_tiles = self.count_full_rows()
        if count != self.full_rows:
            for i in range(count - self.full_rows):
                y = self.options["tile"]["top_y"] - self.scrolling +  i * self.options["tile"]["w"]
                self.tiles.append(
                    EdgeTile(
                        Vector(0, y),
                        self.options["tile"],
                        self.options["tile"]["edge_color"],
                    )
                )
                self.tiles.append(
                    EdgeTile(
                        Vector(self.options["window"]["width"] - self.options["tile"]["w"], y),
                        self.options["tile"],
                        self.options["tile"]["edge_color"],
                    )
                )
            self.scrolling += self.options["tile"]["w"] * (count - self.full_rows)
            self.full_rows = count

        # TODO: better solution than dividing by 10
        if abs(self.scrolling) > self.options["tile"]["w"] / self.options["game"]["scroll_divisor"]:
            scroll_dist = (
                self.delta * self.options["game"]["scroll_speed"] * get_sign(self.scrolling)
            )
            self.scrolling -= scroll_dist
            to_scroll: list[Movable] = self.tiles + self.coins + self.effects  # type: ignore
            for ts in to_scroll:
                ts.scroll(scroll_dist)
            self.player.pt.y += scroll_dist
        elif count > self.options["tile"]["row_limit"]:
            for tile in tiles_to_remove:
                self.tiles.remove(tile)
            for tile in below_tiles:  # TODO!
                tile.pt.y -= tile.h
            self.full_rows -= 1
            self.display_rows -= 1
        if count < self.options["tile"]["row_min"]:
            tile_y = below_tiles[0].pt.y
            for i in range(1, self.options["tile"]["columns"] - 1):
                self.tiles.append(
                    Tile(
                        Vector(i * self.options["tile"]["w"], tile_y),
                        self.options["tile"],
                        self.options["tile"]["color"],
                    )
                )
            self.tiles.append(
                EdgeTile(
                    Vector(0, tile_y), self.options["tile"], self.options["tile"]["edge_color"]
                )
            )
            self.tiles.append(
                EdgeTile(
                    Vector(self.options["window"]["width"] - self.options["tile"]["w"], tile_y),
                    self.options["tile"],
                    self.options["tile"]["edge_color"],
                )
            )
            for tile in below_tiles:  # TODO!
                tile.pt.y += tile.h
            self.full_rows += 1
            self.display_rows += 1

        if self.tile_spawn.update(self.ticks):
            # TODO: clean the types here - why is union[X, None] needed?
            new_tile: Union[Tile, None] = None
            if random.random() < self.options["tile"]["heavy"]["chance"]:
                new_tile = HeavyTile(
                    Vector(
                        random.choice(self.options["tile"]["spawn_xs"]),
                        self.options["tile"]["spawn_y"],
                    ),
                    self.options["tile"],
                )
            elif random.random() < self.options["tile"]["tetris"]["chance"]:
                new_tile = self.drop_tetris_tiles()
                self.tile_spawn.last += self.tile_spawn.period
            else:
                top_tiles = self.find_top_tiles()
                drop_chances = self.calc_drop_chances(top_tiles)
                drop_chance_list: list[float] = []
                for i in range(len(self.options["tile"]["spawn_xs"])):
                    drop_chance_list += [self.options["tile"]["spawn_xs"][i]] * drop_chances[i]
                new_tile = Tile(
                    Vector(random.choice(drop_chance_list), self.options["tile"]["spawn_y"]),
                    self.options["tile"],
                    self.options["tile"]["color"],
                )
            self.tiles.append(new_tile)
            chest_chance = min(
                (
                    (self.options["chest"]["chance_base"] + self.options["chest"]["chance_max"])
                    / self.options["chest"]["chance_time"]
                )
                * self.ticks
                + self.options["chest"]["chance_base"],
                self.options["chest"]["chance_max"],
            )
            if self.save["power"] == "chest_spawn":
                chest_chance *= self.player.powers["chest_spawn"]["increase"]
            if random.random() < chest_chance:
                self.chests.append(Chest(self.options["chest"], new_tile))

            self.tile_spawn.period = max(
                self.options["tile"]["spawn_interval_base"]
                + self.tile_spawn_log_rate * math.log(self.ticks + 1, 10),
                self.options["tile"]["spawn_interval_min"],
            )

        if self.coin_spawn.update(self.ticks):
            self.coins.append(
                Coin(
                    Vector(
                        random.uniform(
                            self.options["tile"]["w"],
                            self.options["window"]["width"]
                            - self.options["tile"]["w"]
                            - self.options["coin"]["w"],
                        ),
                        self.options["coin"]["spawn_y"],
                    ),
                    self.options["coin"],
                )
            )
        self.ticks += self.delta

    def draw_darken(self, win: pygame.surface.Surface) -> None:
        darken_rect = pygame.Surface((win.get_width(), win.get_height()), pygame.SRCALPHA)
        darken_rect.fill((0, 0, 0, self.options["game"]["darken_alpha"]))
        win.blit(darken_rect, (0, 0))

    def draw_death(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        self.draw_darken(win)
        draw_centered_texts(self, win, fonts, "death", self.options["death"].keys())

    def draw_pause(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        self.draw_darken(win)
        draw_centered_texts(self, win, fonts, "pause", self.options["pause"].keys())

    def active_power_type(self) -> bool:
        return self.save["power"] in ["shield", "downthrust"]

    def update_passive_highlight(self) -> None:
        self.passive_highlight += self.delta * 120
        self.passive_highlight = self.passive_highlight % 360

    def draw_hud(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        percent: float = 1
        cd_color: str = self.options["game"]["cd_box"]["color"]
        if self.active_power_type():
            percent = self.player.power_cd / self.player.powers[self.save["power"]]["cd"]
            if percent == 1:
                cd_color = self.options["game"]["cd_box"]["ready_color"]

        pt = Vector(self.options["game"]["cd_box"]["x"], self.options["game"]["cd_box"]["y"])
        box_rect = pygame.Rect(
            pt.get_tuple(),
            (self.options["game"]["cd_box"]["w"], self.options["game"]["cd_box"]["h"]),
        )
        cd_rect = pygame.Rect(
            (pt.x, pt.y + self.options["game"]["cd_box"]["h"] * (1 - percent)),
            (self.options["game"]["cd_box"]["w"], self.options["game"]["cd_box"]["h"] * percent),
        )
        pygame.draw.rect(win, self.options["colors"]["text"], box_rect)
        pygame.draw.rect(win, cd_color, cd_rect)
        pygame.draw.rect(win, self.options["colors"]["text"], box_rect, 3)

        if self.active_power_type():
            surf_cd = fonts["h4"].render(
                self.options["game"]["cd_box"]["text"]
                % (self.player.powers[self.save["power"]]["cd"] - self.player.power_cd),
                True,
                self.options["colors"]["background"],
            )
            text_pt = pt.add(
                Vector(
                    (self.options["game"]["cd_box"]["w"] - surf_cd.get_width()) / 2,
                    (self.options["game"]["cd_box"]["h"] - surf_cd.get_height()) / 2,
                )
            )
            win.blit(surf_cd, text_pt.get_tuple())
        elif self.save["power"] != "none":
            hb = Hitbox(Vector(box_rect[0], box_rect[1]), box_rect[2], box_rect[3], "#ffffff")
            pt_1 = hb.get_center()
            pt_2 = Vector(hb.w * 2, hb.w * 2)
            pt_2.set_angle(self.passive_highlight)
            pt_2 = pt_1.add(pt_2)
            touch = line_hollow_rect_collide(hb, pt_1, pt_2).add(hb.pt)
            pygame.draw.circle(win, self.options["colors"]["text"], touch.get_int_tuple(), 5)

        text_keys = ["score", "rows", "time"]
        text_format = [self.score, max(0, self.full_rows - self.display_rows), int(self.ticks)]
        for i in range(len(text_keys)):
            draw_centered_text(
                win,
                fonts[self.options["game"][text_keys[i]]["font"]],
                self.options["game"][text_keys[i]]["text"] % text_format[i],
                self.options["game"][text_keys[i]]["y"],
                self.options["colors"]["text"],
            )

        if self.fps_draw.update(self.ticks):
            self.display_fps = int(1 / self.delta)

        surf_fps = fonts[self.options["game"]["fps"]["font"]].render(
            self.options["game"]["fps"]["text"] % self.display_fps,
            True,
            self.options["colors"]["text"],
        )
        win.blit(surf_fps, ((self.options["game"]["fps"]["x"], self.options["game"]["fps"]["y"])))

        surf_tiles = fonts[self.options["game"]["tiles"]["font"]].render(
            self.options["game"]["tiles"]["text"] % len(self.tiles),
            True,
            self.options["colors"]["text"],
        )
        win.blit(
            surf_tiles, ((self.options["game"]["tiles"]["x"], self.options["game"]["tiles"]["y"]))
        )

        surf_lives = fonts[self.options["game"]["lives"]["font"]].render(
            self.options["game"]["lives"]["text"],
            True,
            self.options["colors"]["text"],
        )
        win.blit(
            surf_lives, ((self.options["game"]["lives"]["x"], self.options["game"]["lives"]["y"]))
        )
        for i in range(self.player.lives):
            pygame.draw.rect(
                win,
                self.options["game"]["life_boxes"]["color"],
                (
                    surf_lives.get_width()
                    + self.options["game"]["lives"]["x"]
                    + self.options["game"]["life_boxes"]["spacing"] * (i + 1)
                    - self.options["game"]["life_boxes"]["w"],
                    (
                        surf_lives.get_height()
                        - self.options["game"]["life_boxes"]["h"]
                        + self.options["game"]["lives"]["y"]
                    )
                    / 2,
                    self.options["game"]["life_boxes"]["w"],
                    self.options["game"]["life_boxes"]["h"],
                ),
            )

    def draw_powers(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        if self.left_tk.down(self.keys["left"].down(self.keys_down)):
            self.power_choice -= 1
        elif self.right_tk.down(self.keys["right"].down(self.keys_down)):
            self.power_choice += 1

        self.power_choice %= 5
        selected_power = self.powers[self.power_choice]

        text_keys = ["title", "gold", "current", "cost", "details", "controls", "buy", "back"]
        text_format = [
            (),
            (self.save["gold"]),
            (self.player.powers[selected_power]["text"]),
            (self.player.powers[selected_power]["cost"]),
            (),
            (),
            (),
            (),
        ]
        if selected_power in self.save["unlocked"]:
            text_keys[3] = "unlocked"
            text_format[3] = ()
            text_keys[6] = "choose"
        elif self.save["gold"] < self.player.powers[selected_power]["cost"]:
            text_keys[6] = "expensive"
        else:
            if self.keys_down[pygame.K_u]:
                self.save["gold"] -= self.player.powers[selected_power]["cost"]
                self.save["unlocked"].append(selected_power)
                write_json(self.options["save_file"], self.save)

        for i in range(len(text_keys)):
            draw_centered_text(
                win,
                fonts[self.options["powers"][text_keys[i]]["font"]],
                self.options["powers"][text_keys[i]]["text"] % text_format[i],
                self.options["powers"][text_keys[i]]["y"],
                self.options["colors"]["text"],
            )
        for i in range(len(self.player.powers[selected_power]["details"])):
            draw_centered_text(
                win,
                fonts[self.options["powers"]["ability_details"]["font"]],
                self.player.powers[selected_power]["details"][str(i)],
                self.options["powers"]["ability_details"]["y"]
                + i * self.options["powers"]["ability_details"]["spacing"],
                self.options["colors"]["text"],
            )

    def after_intro(self) -> None:
        if self.save["first_boot"]:
            self.save["first_boot"] = False
            write_json(self.options["save_file"], self.save)
            self.screen = "instructions"
        else:
            self.screen = "welcome"

    def draw_intro(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        y_move = (
            -self.ticks * self.options["intro"]["scroll_speed"]
            - self.options["intro"]["scroll_offset"]
        )
        for i in range(len(self.options["intro"]["scrolling_text"])):
            draw_centered_text(
                win,
                fonts[self.options["intro"]["scrolling_text"][str(i)]["font"]],
                self.options["intro"]["scrolling_text"][str(i)]["text"],
                self.options["intro"]["scrolling_text"][str(i)]["y"] + y_move,
                self.options["colors"]["text"],
            )

        pygame.draw.rect(
            win,
            self.options["colors"]["background"],
            (
                (0, self.options["intro"]["still_text"]["background"]["y"]),
                (win.get_width(), self.options["intro"]["still_text"]["background"]["h"]),
            ),
        )
        draw_centered_text(
            win,
            fonts[self.options["intro"]["still_text"]["skip"]["font"]],
            self.options["intro"]["still_text"]["skip"]["text"],
            self.options["intro"]["still_text"]["skip"]["y"],
            self.options["colors"]["text"],
        )

        if y_move <= -self.options["intro"]["stop"]:
            self.after_intro()
        self.ticks += self.delta

    def draw_welcome(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        text_keys = list(self.options["welcome"].keys())
        text_format = [(), (self.save["high_score"]), (self.save["gold"]), (), (), (), ()]
        if self.save["high_score"] == -1:
            text_keys.remove("high_score")
            text_format.remove((self.save["high_score"]))
        for i in range(len(text_keys)):
            draw_centered_text(
                win,
                fonts[self.options["welcome"][text_keys[i]]["font"]],
                self.options["welcome"][text_keys[i]]["text"] % text_format[i],
                self.options["welcome"][text_keys[i]]["y"],
                self.options["colors"]["text"],
            )

    def draw_instructions(
        self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]
    ) -> None:
        draw_centered_texts(self, win, fonts, "instructions", self.options["instructions"].keys())


def get_sign(x: float) -> int:
    if x == 0:
        return 0
    elif x > 0:
        return 1
    else:
        return -1


def circle_rect_collide(rect: Hitbox, center: Vector, r: float) -> bool:
    # Yes this was easier than doing the math
    circle_surf = pygame.Surface((r * 2, r * 2))
    circle_surf.fill((0, 0, 255))
    circle_surf.set_colorkey((0, 0, 255))
    pygame.draw.circle(circle_surf, (255, 0, 0), (r, r), r)
    circle_mask = pygame.mask.from_surface(circle_surf)

    rect_surf = pygame.Surface((rect.w, rect.h))
    rect_surf.fill((255, 0, 0))
    rect_mask = pygame.mask.from_surface(rect_surf)

    touch = circle_mask.overlap(
        rect_mask, rect.pt.subtract(center.subtract(Vector(r, r))).get_int_tuple()
    )
    return touch != None


def line_hollow_rect_collide(rect: Hitbox, pt_1: Vector, pt_2: Vector) -> Vector:
    rect_surf = pygame.Surface((rect.w, rect.h))
    rect_surf.fill((0, 0, 255))
    rect_surf.set_colorkey((0, 0, 255))
    pygame.draw.rect(rect_surf, (255, 0, 0), (0, 0, int(rect.w), int(rect.h)), 2)
    rect_mask = pygame.mask.from_surface(rect_surf)

    line_surf = pygame.Surface((rect.w, rect.h))
    line_surf.fill((0, 0, 255))
    line_surf.set_colorkey((0, 0, 255))
    pt_1 = pt_1.subtract(rect.pt)
    pt_2 = pt_2.subtract(rect.pt)
    pygame.draw.line(line_surf, (255, 0, 0), pt_1.get_int_tuple(), pt_2.get_int_tuple())
    line_mask = pygame.mask.from_surface(line_surf)

    touch = rect_mask.overlap_mask(line_mask, (0, 0)).centroid()
    return Vector(touch[0], touch[1])


def read_json(path: str) -> dict:
    print("Reading from", path)
    with open(path, "r") as f:
        return json.load(f)


def write_json(path: str, data: dict) -> None:
    print("Writing to", path)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def create_window(options: dict[str, Any]) -> pygame.surface.Surface:
    pygame.init()
    win = pygame.display.set_mode(
        (options["window"]["width"], options["window"]["height"]), pygame.SCALED
    )
    pygame.display.set_caption(options["title"])  # TODO: icon
    return win


def create_fonts(font_options: dict[str, Any]) -> dict[str, pygame.font.Font]:
    fonts: dict[str, pygame.font.Font] = {}
    for size in font_options["size"]:
        fonts[size] = pygame.font.Font(font_options["name"], font_options["size"][size])
    return fonts


def draw_centered_text(
    win: pygame.surface.Surface,
    font: pygame.font.Font,
    text: str,
    y: float,
    color: tuple[int, int, int],
) -> None:
    # TODO/Note: color is actually hex color string, not tuple
    surf_text = font.render(text, True, color)
    win.blit(surf_text, ((win.get_width() - surf_text.get_width()) / 2, y))


def draw_centered_texts(
    state: State,
    win: pygame.surface.Surface,
    fonts: dict[str, pygame.font.Font],
    section: str,
    text_keys: list[str],
) -> None:
    for key in text_keys:
        draw_centered_text(
            win,
            fonts[state.options[section][key]["font"]],
            state.options[section][key]["text"],
            state.options[section][key]["y"],
            state.options["colors"]["text"],
        )


def main():
    options = read_json("resources/options.json")
    save = read_json(options["save_file"])
    win = create_window(options)
    fonts = create_fonts(options["font"])
    state = State(options, save)
    state.run(win, fonts)


if __name__ == "__main__":
    main()
