from __future__ import annotations
from typing import Any, Sequence, Union

import pygame

import math
import time
import json
import random
import copy
import multiprocessing


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

        if (state.player.alive and self.collide(state.player)) or not self.bot_tile in state.tiles:
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
        self.thrust_vel: float = options["player"]["thrust_vel"]
        self.jumps: int = 1
        self.space_tk: ToggleKey = ToggleKey(True)
        self.s_tk: ToggleKey = ToggleKey()
        self.alive: bool = True

    def key_input(self, keys_down: Sequence[bool], keys: dict[str, KeyList]) -> None:
        self.move_vec.x = 0
        if keys["right"].down(keys_down):
            self.move_vec.x = self.speed
        elif keys["left"].down(keys_down):
            self.move_vec.x = -self.speed

        if self.space_tk.down(keys["up"].down(keys_down)) and self.jumps < 2:
            self.move_vec.y = -self.jump_vel
            self.jumps += 1
        elif self.s_tk.down(keys["down"].down(keys_down)):
            self.move_vec.y += self.thrust_vel

    def check_tile_collision(self, tile_map: dict[str, list[Tile]], tile_size: int) -> None:
        current_self: Player = copy.deepcopy(self)  # TODO: not sure if the copy is needed

        map_tup = self.pt.get_map_tup(tile_size)
        map_xs = [map_tup[0], map_tup[0] + 1]
        map_ys = [map_tup[1] - 1, map_tup[1], map_tup[1] + 1]
        for x in map_xs:
            for y in map_ys:
                map_str = str(x) + ";" + str(y)
                try:
                    for tile in tile_map[map_str]:
                        collision = tile.directional_collide(current_self)
                        if collision == "bottom":
                            self.alive = False
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

    def update(self, state: State) -> None:
        if self.alive:
            self.key_input(state.keys_down, state.keys)

            if self.pt.x < state.options["tile"]["w"]:
                self.pt.x = state.options["tile"]["w"]
            elif self.pt.x + self.w + state.options["tile"]["w"] > state.options["window"]["width"]:
                self.pt.x = state.options["window"]["width"] - self.w - state.options["tile"]["w"]

            self.move(state.delta)
            self.check_tile_collision(state.tile_map, state.options["tile"]["w"])
        else:
            self.color = state.options["player"]["dead_color"]


class Tile(Movable):
    def __init__(
        self,
        pt: Vector,
        tile_options: dict[str, Any],
        tile_settings: dict[str, Any],
        color: str,
    ):
        super().__init__(
            pt,
            tile_options["w"],
            tile_options["w"],
            color,
            Vector(0, tile_settings["fall_speed"]),
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
        self.move(state.delta)
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
    def __init__(
        self, pt: Vector, tile_options: dict[str, Any], tile_settings: dict[str, Any], color: str
    ):
        super().__init__(pt, tile_options, tile_settings, color)
        self.move_vec.y = 0


class HeavyTile(Tile):
    def __init__(self, pt: Vector, tile_options: dict[str, Any], tile_settings: dict[str, Any]):
        super().__init__(pt, tile_options, tile_settings, tile_options["heavy"]["color"])
        self.move_vec.y *= tile_settings["heavy"]["fall"]

    def check_explosion_tiles(self, state: State) -> None:
        pass
        map_tup = self.pt.get_map_tup(state.options["tile"]["w"])
        map_xs = [map_tup[0] - 1, map_tup[0], map_tup[0] + 1]
        map_ys = [map_tup[1] - 1, map_tup[1], map_tup[1] + 1]
        for x in map_xs:
            for y in map_ys:
                map_str = str(x) + ";" + str(y)
                try:
                    for i in range(len(state.tile_map[map_str]) - 1, -1, -1):
                        if type(state.tile_map[map_str][i]) != EdgeTile and circle_rect_collide(
                            state.tile_map[map_str][i],
                            self.get_center(),
                            state.settings["tile"]["heavy"]["r"],
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
                            state.player, self.get_center(), state.settings["tile"]["heavy"]["r"]
                        ):
                            state.player.alive = False

                        state.effects.append(
                            CircleEffect(
                                self.get_center(),
                                state.settings["tile"]["heavy"]["r"],
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
        move_vec: Vector,
        gravity: float = 0,
    ):
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
                            self.move_vec.y = 0
                        elif collision == "left":
                            self.pt.x = tile.pt.x - self.w
                            self.move_vec.x = 0
                        elif collision == "right":
                            self.pt.x = tile.pt.x + tile.w
                            self.move_vec.x = 0
                except KeyError:
                    pass

        if state.player.alive and self.move_vec.y >= 0 and self.collide(state.player):
            state.coins.remove(self)  # TODO: remove in iteration?
            state.score += 1


class State:
    def __init__(self, options: dict[str, Any], settings: dict[str, Any]):
        self.options: dict[str, Any] = options
        self.settings: dict[str, Any] = settings
        self.paused: bool = False
        self.screen: str = "welcome"
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
        self.scrolling: float = 0
        self.full_rows: int = 3
        self.display_rows: int = 3
        self.tile_spawn: Interval = Interval(
            self.settings["tile"]["spawn_interval_base"], self.ticks
        )
        self.tile_spawn_log_rate: float = (
            self.settings["tile"]["spawn_interval_min"]
            - self.settings["tile"]["spawn_interval_base"]
        ) / math.log(self.settings["tile"]["spawn_interval_time"] + 1, 10)
        self.coin_spawn: RandomInterval = RandomInterval(
            self.settings["coin"]["spawn_interval_base"],
            self.settings["coin"]["spawn_interval_variance"],
            self.ticks,
        )
        self.fps_draw: Interval = Interval(self.options["game"]["fps"]["refresh"], self.ticks)
        self.display_fps: int = 500
        self.esc_tk: ToggleKey = ToggleKey()
        self.down_tk: ToggleKey = ToggleKey()
        self.up_tk: ToggleKey = ToggleKey()
        self.playing: bool = True
        self.selected_setting: int = 0

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
                        self.settings["tile"],
                        self.options["tile"]["edge_color"]
                        if tile_types[j] == EdgeTile
                        else self.options["tile"]["color"],
                    )
                )

        tile_y += (len(tile_types) - 1) * self.options["tile"]["w"]
        while tile_y > -self.options["tile"]["w"]:
            self.tiles.append(
                EdgeTile(
                    Vector(0, tile_y),
                    self.options["tile"],
                    self.settings["tile"],
                    self.options["tile"]["edge_color"],
                )
            )
            self.tiles.append(
                EdgeTile(
                    Vector(self.options["window"]["width"] - self.options["tile"]["w"], tile_y),
                    self.options["tile"],
                    self.settings["tile"],
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

        if self.screen == "welcome":
            if self.keys["up"].down(self.keys_down):
                self.reset()
                self.screen = "game"
            elif self.keys_down[pygame.K_i]:
                self.screen = "instructions"
            elif self.keys_down[pygame.K_s]:
                self.screen = "settings"
            elif self.keys_down[pygame.K_ESCAPE]:
                self.exit()
        elif self.screen == "instructions":
            if self.keys_down[pygame.K_b]:
                self.screen = "welcome"
        elif self.screen == "settings":
            if self.keys_down[pygame.K_b]:
                self.screen = "welcome"
            elif self.keys_down[pygame.K_RETURN]:
                self.screen = ["tile", "coin", "chest"][self.selected_setting]
        elif self.screen == "game":
            if self.esc_tk.down(self.keys_down[pygame.K_ESCAPE]):
                self.paused = not self.paused
            elif (not self.player.alive and self.keys_down[pygame.K_r]) or (
                self.paused and self.keys_down[pygame.K_q]
            ):
                self.screen = "welcome"

    def next_frame(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]):
        win.fill(self.options["colors"]["background"])

        if self.screen == "welcome":
            self.draw_welcome(win, fonts)
        elif self.screen == "instructions":
            self.draw_instructions(win, fonts)
        elif self.screen == "settings":
            self.update_settings()
            self.draw_settings(win, fonts)
        elif self.screen == "game":
            if not self.paused:
                self.update_game()
            self.draw_game(win, fonts)

        pygame.display.update()

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
        elif not self.player.alive:
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

    def calc_drop_chances(self) -> list[int]:
        top_tiles: list[float] = []
        for _ in self.options["tile"]["spawn_xs"]:
            top_tiles.append(self.options["tile"]["base_y"] - self.options["tile"]["w"])
        for tile in self.tiles:  # TODO!
            if type(tile) != EdgeTile:
                idx = self.options["tile"]["spawn_xs"].index(tile.pt.x)
                if top_tiles[idx] > tile.pt.y:
                    top_tiles[idx] = tile.pt.y

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

    def update_game(self) -> None:
        self.create_tile_map()
        # Prob some way to do this without the '# type: ignore'
        entities: list[Hitbox] = self.tiles + self.chests + self.coins + self.effects + [self.player]  # type: ignore
        for e in entities:
            e.update(self)

        count, tiles_to_remove, below_tiles = self.count_full_rows()
        if count != self.full_rows:
            if count > self.full_rows:
                self.tiles.append(
                    EdgeTile(
                        Vector(0, self.options["tile"]["top_y"] - self.scrolling),
                        self.options["tile"],
                        self.settings["tile"],
                        self.options["tile"]["edge_color"],
                    )
                )
                self.tiles.append(
                    EdgeTile(
                        Vector(
                            self.options["window"]["width"] - self.options["tile"]["w"],
                            self.options["tile"]["top_y"] - self.scrolling,
                        ),
                        self.options["tile"],
                        self.settings["tile"],
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
            to_scroll: list[Moveable] = self.tiles + self.coins + self.effects  # type: ignore
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
                        self.settings["tile"],
                        self.options["tile"]["color"],
                    )
                )
            self.tiles.append(
                EdgeTile(
                    Vector(0, tile_y),
                    self.options["tile"],
                    self.settings["tile"],
                    self.options["tile"]["edge_color"],
                )
            )
            self.tiles.append(
                EdgeTile(
                    Vector(self.options["window"]["width"] - self.options["tile"]["w"], tile_y),
                    self.options["tile"],
                    self.settings["tile"],
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
            heavy_chance = random.random()
            if heavy_chance < self.settings["tile"]["heavy"]["chance"]:
                new_tile = HeavyTile(
                    Vector(
                        random.choice(self.options["tile"]["spawn_xs"]),
                        self.options["tile"]["spawn_y"],
                    ),
                    self.options["tile"],
                    self.settings["tile"],
                )
            else:
                drop_chances = self.calc_drop_chances()
                drop_chance_list: list[float] = []
                for i in range(len(self.options["tile"]["spawn_xs"])):
                    drop_chance_list += [self.options["tile"]["spawn_xs"][i]] * drop_chances[i]
                new_tile = Tile(
                    Vector(random.choice(drop_chance_list), self.options["tile"]["spawn_y"]),
                    self.options["tile"],
                    self.settings["tile"],
                    self.options["tile"]["color"],
                )
            self.tiles.append(new_tile)
            chest_chance = random.random()
            if chest_chance < self.settings["chest"]["spawn_chance"]:
                self.chests.append(Chest(self.options["chest"], new_tile))

            self.tile_spawn.period = max(
                self.settings["tile"]["spawn_interval_base"]
                + self.tile_spawn_log_rate * math.log(self.ticks + 1, 10),
                self.settings["tile"]["spawn_interval_min"],
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
                    Vector(0, self.settings["coin"]["fall_speed"]),
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

    def draw_hud(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
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

        surf_fps = fonts["h5"].render(
            self.options["game"]["fps"]["text"] % self.display_fps,
            True,
            self.options["colors"]["text"],
        )
        win.blit(surf_fps, ((self.options["game"]["fps"]["x"], self.options["game"]["fps"]["y"])))

        surf_tiles = fonts["h5"].render(
            self.options["game"]["tiles"]["text"] % len(self.tiles),
            True,
            self.options["colors"]["text"],
        )
        win.blit(
            surf_tiles, ((self.options["game"]["tiles"]["x"], self.options["game"]["tiles"]["y"]))
        )

    def draw_welcome(self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        text_keys = list(self.options["welcome"].keys())
        text_format = [(), (self.score), (), (), (), ()]
        if self.score == -1:
            text_keys.remove("score")
            text_format.remove((self.score))
        for i in range(len(text_keys)):
            draw_centered_text(
                win,
                fonts[self.options["welcome"][text_keys[i]]["font"]],
                self.options["welcome"][text_keys[i]]["text"] % text_format[i],
                self.options["welcome"][text_keys[i]]["y"],
                self.options["colors"]["text"],
            )

    def update_settings(self) -> None:
        if self.up_tk.down(self.keys_down[pygame.K_UP]) and self.selected_setting > 0:
            self.selected_setting -= 1
        elif (
            self.down_tk.down(self.keys_down[pygame.K_DOWN])
            and self.selected_setting < self.options["settings"]["setting_menu_count"] - 1
        ):
            self.selected_setting += 1

    def draw_settings(
        self, win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font]
    ) -> None:

        selected_rect = pygame.Rect(
            (
                (win.get_width() - self.options["settings"]["w"]) / 2,
                self.options["settings"]["y_top"]
                + self.selected_setting * self.options["settings"]["y_spacing"],
            ),
            (self.options["settings"]["w"], self.options["settings"]["h"]),
        )
        pygame.draw.rect(win, self.options["settings"]["selected_box_color"], selected_rect)

        text_keys = ["title", "tile", "coin", "coin", "chest", "back"]
        draw_centered_texts(self, win, fonts, "settings", text_keys)

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


def read_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


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
    settings = read_json("resources/settings.json")
    win = create_window(options)
    fonts = create_fonts(options["font"])
    state = State(options, settings)
    state.run(win, fonts)


if __name__ == "__main__":
    main()
