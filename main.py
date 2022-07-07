from __future__ import annotations
from typing import Any, Union
from dataclasses import dataclass  # struct like classes

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


@dataclass  # auto writes __init__ and __repr__
class State:
    # TODO: float/ints defaults?
    win: pygame.surface.Surface
    fonts: dict[str, pygame.font.Font]
    options: dict[str, Any]
    map_dict: dict[str, list[Hitbox]]
    paused: bool
    screen: str
    keys_down: list[bool]
    player: Player
    tiles: list[Tile]
    coins: list[Coin]
    chests: list[Chest]
    effects: list[Effect]
    delta: float
    ticks: float
    score: int
    scrolling: float
    full_rows: int
    display_rows: int
    tile_spawn: Interval
    tile_spawn_log_rate: float
    coin_spawn: RandomInterval
    fps_draw: Interval
    display_fps: int
    esc_tk: ToggleKey
    playing: bool


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
                for e in state.map_dict[map_str]:
                    if e != self and (type(e) == Tile or type(e) == HeavyTile):
                        collision = e.directional_collide(self)
                        if collision == "bottom":
                            state.chests.remove(self)
                            return
            except KeyError:
                pass

        if (state.player.alive and self.collide(state.player)) or not self.bot_tile in state.tiles:
            state.chests.remove(self)
            num_coins = random.choice(state.options["coin"]["pop"]["coin_chances"])
            for _ in range(num_coins):
                c = Coin(self.get_center(), state.options["coin"])
                c.move_vec = Vector(
                    random.uniform(
                        -state.options["coin"]["pop"]["speed"],
                        state.options["coin"]["pop"]["speed"],
                    ),
                    -state.options["coin"]["pop"]["vel"],
                )
                c.move_vec.scale(state.options["coin"]["pop"]["vel"])
                c.gravity = state.options["coin"]["pop"]["gravity"]
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
            state.effects.remove(self)


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

    def key_input(self, keys_down: list[bool]) -> None:
        self.move_vec.x = 0
        if keys_down[pygame.K_d] or keys_down[pygame.K_RIGHT]:
            self.move_vec.x = self.speed
        elif keys_down[pygame.K_a] or keys_down[pygame.K_LEFT]:
            self.move_vec.x = -self.speed

        if (
            self.space_tk.down(
                keys_down[pygame.K_SPACE] or keys_down[pygame.K_UP] or keys_down[pygame.K_w]
            )
            and self.jumps < 2
        ):
            self.move_vec.y = -self.jump_vel
            self.jumps += 1
        elif self.s_tk.down(keys_down[pygame.K_s] or keys_down[pygame.K_DOWN]):
            self.move_vec.y += self.thrust_vel

    def check_tile_collision(self, map_dict: dict[str, list[Hitbox]], tile_size: int) -> None:
        current_self: Player = copy.deepcopy(self)  # TODO: not sure if the copy is needed

        map_tup = self.pt.get_map_tup(tile_size)
        map_xs = [map_tup[0], map_tup[0] + 1]
        map_ys = [map_tup[1] - 1, map_tup[1], map_tup[1] + 1]
        for x in map_xs:
            for y in map_ys:
                map_str = str(x) + ";" + str(y)
                try:
                    for e in map_dict[map_str]:
                        if e != self and (
                            type(e) == Tile or type(e) == EdgeTile or type(e) == HeavyTile
                        ):
                            collision = e.directional_collide(current_self)
                            if collision == "bottom":
                                self.alive = False
                            elif collision == "top":
                                self.pt.y = e.pt.y - self.h
                                self.move_vec.y = 0
                                self.jumps = 0
                                self.space_tk.down(False)
                            elif collision == "left":
                                self.pt.x = e.pt.x - self.w
                            elif collision == "right":
                                self.pt.x = e.pt.x + e.w
                except KeyError:
                    pass

    def update(self, state: State) -> None:
        if self.alive:
            self.key_input(state.keys_down)

            if self.pt.x < state.options["tile"]["w"]:
                self.pt.x = state.options["tile"]["w"]
            elif self.pt.x + self.w + state.options["tile"]["w"] > state.win.get_width():
                self.pt.x = state.win.get_width() - self.w - state.options["tile"]["w"]

            self.move(state.delta)
            self.check_tile_collision(state.map_dict, state.options["tile"]["w"])
        else:
            self.color = state.options["player"]["dead_color"]


class Fall(Movable):
    def __init__(self, pt: Vector, w: float, h: float, color: str, fall_speed: float):
        super().__init__(pt, w, h, color, Vector(0, fall_speed), 0)


class Tile(Fall):
    def __init__(
        self,
        pt: Vector,
        tile_options: dict[str, Any],
        color: str,
    ):
        super().__init__(
            pt, tile_options["w"], tile_options["w"], color, tile_options["fall_speed"]
        )  # TODO: color
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
                for e in state.map_dict[map_str]:
                    if e != self and (type(e) == Tile or type(e) == EdgeTile) and self.collide(e):
                        self.pt.y = e.pt.y - self.h
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

    def land(self, state: State) -> None:
        for tile in state.tiles:  # TODO!
            if tile != self and self.collide(tile):
                state.tiles.remove(self)
                for tile2 in state.tiles:  # TODO!
                    if type(tile2) != EdgeTile:
                        tile_collide = circle_rect_collide(
                            tile2, self.get_center(), state.options["tile"]["heavy"]["r"]
                        )
                        if tile_collide:
                            state.tiles.remove(tile2)

                player_collide = circle_rect_collide(
                    state.player, self.get_center(), state.options["tile"]["heavy"]["r"]
                )

                if player_collide:
                    state.player.alive = False

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

                break


class Coin(Fall):
    def __init__(self, pt: Vector, coin_options: dict[str, Any]):
        super().__init__(
            pt,
            coin_options["w"],
            coin_options["h"],
            coin_options["color"],
            coin_options["fall_speed"],
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
                    for e in state.map_dict[map_str]:
                        if e != self and (
                            type(e) == Tile or type(e) == EdgeTile or type(e) == HeavyTile
                        ):
                            collision = e.directional_collide(self)
                            if collision == "bottom":
                                state.coins.remove(self)
                                return  # avoid double-removal chance
                            elif collision == "top":
                                self.pt.y = e.pt.y - self.h + 1  # TODO: does this need a +1?
                                self.move_vec.x -= (
                                    state.options["coin"]["pop"]["friction"]
                                    * state.delta
                                    * get_sign(self.move_vec.x)
                                )
                                self.move_vec.y = 0
                            elif collision == "left":
                                self.pt.x = e.pt.x - self.w
                                self.move_vec.x = 0
                            elif collision == "right":
                                self.pt.x = e.pt.x + e.w
                                self.move_vec.x = 0
                except KeyError:
                    pass

        if state.player.alive and self.move_vec.y >= 0 and self.collide(state.player):
            state.coins.remove(self)
            state.score += 1


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


def read_options(path: str) -> dict:
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
    return {
        "h1": pygame.font.Font(font_options["name"], font_options["size"]["h1"]),
        "h2": pygame.font.Font(font_options["name"], font_options["size"]["h2"]),
        "h3": pygame.font.Font(font_options["name"], font_options["size"]["h3"]),
        "h4": pygame.font.Font(font_options["name"], font_options["size"]["h4"]),
        "h5": pygame.font.Font(font_options["name"], font_options["size"]["h5"]),
    }


def handle_events(state: State) -> None:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            state.playing = False

    if state.screen == "welcome":
        if state.keys_down[pygame.K_SPACE]:
            reset(state)
            state.screen = "game"
        elif state.keys_down[pygame.K_i]:
            state.screen = "instructions"
        elif state.keys_down[pygame.K_ESCAPE]:
            pygame.quit()
            state.playing = False
    elif state.screen == "instructions":
        if state.keys_down[pygame.K_ESCAPE]:
            state.screen = "welcome"
    elif state.screen == "game":
        if state.esc_tk.down(state.keys_down[pygame.K_ESCAPE]):
            state.paused = not state.paused
        elif (not state.player.alive and state.keys_down[pygame.K_r]) or (
            state.paused and state.keys_down[pygame.K_q]
        ):
            state.screen = "welcome"


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


def draw_welcome(state: State) -> None:
    draw_centered_text(
        state.win,
        state.fonts["h1"],
        state.options["title"],
        state.options["welcome"]["title"]["y"],
        state.options["colors"]["text"],
    )
    if state.score != -1:
        draw_centered_text(
            state.win,
            state.fonts["h4"],
            state.options["welcome"]["score"]["text"] % state.score,
            state.options["welcome"]["score"]["y"],
            state.options["colors"]["text"],
        )
    draw_centered_text(
        state.win,
        state.fonts["h3"],
        state.options["welcome"]["start"]["text"],
        state.options["welcome"]["start"]["y"],
        state.options["colors"]["text"],
    )
    draw_centered_text(
        state.win,
        state.fonts["h4"],
        state.options["welcome"]["instructions"]["text"],
        state.options["welcome"]["instructions"]["y"],
        state.options["colors"]["text"],
    )


def count_full_rows(
    tiles: list[Tile], columns: int, row_limit: int
) -> tuple[int, list[Tile], list[Tile]]:
    tile_ys: dict[float, int] = {}
    for tile in tiles:  # TODO!
        try:
            tile_ys[tile.pt.y] += 1
        except KeyError:
            tile_ys[tile.pt.y] = 1

    count = 0
    for value in tile_ys.values():
        if value == columns:
            count += 1

    third_row_tiles: list[Tile] = []
    below_tiles: list[Tile] = []

    if count > row_limit:
        sorted_keys = sorted(tile_ys.keys(), reverse=True)
        for key in sorted_keys:  # TODO: removing in iteration
            if tile_ys[key] != columns:
                sorted_keys.remove(key)
        third_row_y = sorted_keys[2]
        for tile in tiles:  # TODO!
            if tile.pt.y == third_row_y:
                third_row_tiles.append(tile)
            elif tile.pt.y > third_row_y:
                below_tiles.append(tile)

    return count, third_row_tiles, below_tiles


def calc_drop_chances(state: State) -> list[int]:
    top_tiles: list[float] = []
    for _ in state.options["tile"]["spawn_xs"]:
        top_tiles.append(state.options["tile"]["base_y"] - state.options["tile"]["w"])
    for tile in state.tiles:  # TODO!
        if type(tile) != EdgeTile:
            idx = state.options["tile"]["spawn_xs"].index(tile.pt.x)
            if top_tiles[idx] > tile.pt.y:
                top_tiles[idx] = tile.pt.y

    max_value: float = max(top_tiles)
    min_value: float = min(top_tiles)

    old_range = max_value - min_value
    new_range = state.options["tile"]["spawn_scale_max"] - state.options["tile"]["spawn_scale_min"]

    drop_chances: list[int] = []
    for y in top_tiles:
        if y < 0:
            chance = 0
        else:
            try:
                chance = ((y - min_value) * new_range) / old_range
            except ZeroDivisionError:
                chance = 0
            chance += state.options["tile"]["spawn_scale_min"]
        drop_chances.append(int(chance))

    return drop_chances


def draw_darken(state: State) -> None:
    darken_rect = pygame.Surface((state.win.get_width(), state.win.get_height()), pygame.SRCALPHA)
    darken_rect.fill((0, 0, 0, state.options["game"]["darken_alpha"]))
    state.win.blit(darken_rect, (0, 0))


def draw_death(state: State) -> None:
    draw_darken(state)
    draw_centered_text(
        state.win,
        state.fonts["h2"],
        state.options["death"]["title"]["text"],
        state.options["death"]["title"]["y"],
        state.options["colors"]["text"],
    )
    draw_centered_text(
        state.win,
        state.fonts["h3"],
        state.options["death"]["restart"]["text"],
        state.options["death"]["restart"]["y"],
        state.options["colors"]["text"],
    )


def create_map(state: State) -> None:
    entities: list[Hitbox] = state.tiles + state.chests + state.coins + state.effects + [state.player]  # type: ignore
    state.map_dict = {}
    for e in entities:
        map_str = e.pt.get_map_str(state.options["tile"]["w"])
        try:
            state.map_dict[map_str].append(e)
        except KeyError:
            state.map_dict[map_str] = [e]


def draw_unpause(state: State) -> None:

    create_map(state)

    # Prob some way to do this without the '# type: ignore'
    entities: list[Hitbox] = state.tiles + state.chests + state.coins + state.effects + [state.player]  # type: ignore
    for e in entities:  # TODO!
        e.update(state)
        if e.pt.y < state.win.get_height() and e.pt.y > -e.h:
            e.draw(state.win)

    count, third_row_tiles, below_tiles = count_full_rows(
        state.tiles, state.options["tile"]["columns"], state.options["tile"]["row_limit"]
    )
    if count != state.full_rows:
        if count > state.full_rows:
            state.tiles.append(
                EdgeTile(
                    Vector(0, state.options["tile"]["top_y"] - state.scrolling),
                    state.options["tile"],
                    state.options["tile"]["edge_color"],
                )
            )
            state.tiles.append(
                EdgeTile(
                    Vector(
                        state.options["window"]["width"] - state.options["tile"]["w"],
                        state.options["tile"]["top_y"] - state.scrolling,
                    ),
                    state.options["tile"],
                    state.options["tile"]["edge_color"],
                )
            )
        state.scrolling += state.options["tile"]["w"] * (count - state.full_rows)
        state.full_rows = count

    # TODO: better solution than dividing by 10
    if abs(state.scrolling) > state.options["tile"]["w"] / state.options["game"]["scroll_divisor"]:
        scroll_dist = state.delta * state.options["scroll_speed"] * get_sign(state.scrolling)
        state.scrolling -= scroll_dist
        to_scroll: list[Moveable] = state.tiles + state.coins + state.effects  # type: ignore
        for ts in to_scroll:  # TODO!
            ts.scroll(scroll_dist)
        state.player.pt.y += scroll_dist
    elif count > state.options["tile"]["row_limit"]:
        for tile in third_row_tiles:
            state.tiles.remove(tile)
        for tile in below_tiles:  # TODO!
            tile.pt.y -= tile.h
        state.full_rows -= 1
        state.display_rows -= 1

    if state.tile_spawn.update(state.ticks):
        # TODO: clean the types here - why is union[X, None] needed?
        new_tile: Union[Tile, None] = None
        heavy_chance = random.random()
        if heavy_chance < state.options["tile"]["heavy"]["chance"]:
            new_tile = HeavyTile(
                Vector(
                    random.choice(state.options["tile"]["spawn_xs"]),
                    state.options["tile"]["spawn_y"],
                ),
                state.options["tile"],
            )
        else:
            drop_chances = calc_drop_chances(state)
            drop_chance_list: list[float] = []
            for i in range(len(state.options["tile"]["spawn_xs"])):
                drop_chance_list += [state.options["tile"]["spawn_xs"][i]] * drop_chances[i]
            new_tile = Tile(
                Vector(random.choice(drop_chance_list), state.options["tile"]["spawn_y"]),
                state.options["tile"],
                state.options["tile"]["color"],
            )
        state.tiles.append(new_tile)
        chest_chance = random.random()
        if chest_chance < state.options["chest"]["spawn_chance"]:
            state.chests.append(Chest(state.options["chest"], new_tile))

        state.tile_spawn.period = max(
            state.options["tile"]["spawn_interval_base"]
            + state.tile_spawn_log_rate * math.log(state.ticks + 1, 10),
            state.options["tile"]["spawn_interval_min"],
        )

    if state.coin_spawn.update(state.ticks):
        state.coins.append(
            Coin(
                Vector(
                    random.uniform(
                        state.options["tile"]["w"],
                        state.options["window"]["width"]
                        - state.options["tile"]["w"]
                        - state.options["coin"]["w"],
                    ),
                    state.options["coin"]["spawn_y"],
                ),
                state.options["coin"],
            )
        )


def draw_pause(state: State) -> None:
    draw_darken(state)

    entities: list[Hitbox] = state.tiles + state.chests + state.coins + state.effects + [state.player]  # type: ignore
    for e in entities:
        if e.pt.y < state.win.get_height() and e.pt.y > -e.h:
            e.draw(state.win)

    draw_centered_text(
        state.win,
        state.fonts["h2"],
        state.options["pause"]["title"]["text"],
        state.options["pause"]["title"]["y"],
        state.options["colors"]["text"],
    )
    draw_centered_text(
        state.win,
        state.fonts["h3"],
        state.options["pause"]["resume"]["text"],
        state.options["pause"]["resume"]["y"],
        state.options["colors"]["text"],
    )
    draw_centered_text(
        state.win,
        state.fonts["h4"],
        state.options["pause"]["quit"]["text"],
        state.options["pause"]["quit"]["y"],
        state.options["colors"]["text"],
    )


def draw_hud(state: State) -> None:

    draw_centered_text(
        state.win,
        state.fonts["h4"],
        state.options["game"]["score"]["text"] % state.score,
        state.options["game"]["score"]["y"],
        state.options["colors"]["text"],
    )
    draw_centered_text(
        state.win,
        state.fonts["h5"],
        state.options["game"]["rows"]["text"] % max(0, state.full_rows - state.display_rows),
        state.options["game"]["rows"]["y"],
        state.options["colors"]["text"],
    )
    draw_centered_text(
        state.win,
        state.fonts["h5"],
        state.options["game"]["time"]["text"] % int(state.ticks),
        state.options["game"]["time"]["y"],
        state.options["colors"]["text"],
    )

    if state.fps_draw.update(state.ticks):
        state.display_fps = int(1 / state.delta)

    surf_fps = state.fonts["h5"].render(
        state.options["game"]["fps"]["text"] % state.display_fps,
        True,
        state.options["colors"]["text"],
    )
    state.win.blit(
        surf_fps, ((state.options["game"]["fps"]["x"], state.options["game"]["fps"]["y"]))
    )

    surf_tiles = state.fonts["h5"].render(
        state.options["game"]["tiles"]["text"] % len(state.tiles),
        True,
        state.options["colors"]["text"],
    )
    state.win.blit(
        surf_tiles, ((state.options["game"]["tiles"]["x"], state.options["game"]["tiles"]["y"]))
    )


def draw_game(state: State) -> None:
    if not state.paused:
        draw_unpause(state)
        state.ticks += state.delta

    draw_hud(state)

    if state.paused:
        draw_pause(state)
    elif not state.player.alive:
        draw_death(state)


def setup(options: dict[str, Any]) -> tuple[Player, list[Tile]]:
    player = Player(options)
    tiles: list[Tile] = []

    tile_y = options["tile"]["base_y"]
    tile_types = [Tile, Tile, EdgeTile, EdgeTile]
    for i in range(options["tile"]["columns"] - 2):
        for j in range(len(tile_types)):
            tiles.append(
                tile_types[j](
                    Vector((i + 1) * options["tile"]["w"], tile_y + j * options["tile"]["w"]),
                    options["tile"],
                    options["tile"]["edge_color"]
                    if tile_types[j] == EdgeTile
                    else options["tile"]["color"],
                )
            )

    tile_y += (len(tile_types) - 1) * options["tile"]["w"]
    while tile_y > -options["tile"]["w"]:
        tiles.append(EdgeTile(Vector(0, tile_y), options["tile"], options["tile"]["edge_color"]))
        tiles.append(
            EdgeTile(
                Vector(options["window"]["width"] - options["tile"]["w"], tile_y),
                options["tile"],
                options["tile"]["edge_color"],
            )
        )
        tile_y -= options["tile"]["w"]
        options["tile"]["top_y"] = tile_y  # TODO: change - modifying options

    return player, tiles


def reset(state: State):
    state.player, state.tiles = setup(state.options)
    state.coins = []
    state.chests = []
    state.effects = []
    state.ticks = 1 / 500
    state.scrolling = 0
    state.full_rows = 4
    state.display_rows = 4
    state.paused = False
    state.tile_spawn.reset(state.ticks)
    state.coin_spawn.reset(state.ticks)
    state.fps_draw.reset(state.ticks)
    state.score = 0


def main():

    options = read_options("resources/options.json")
    player, tiles = setup(options)

    state = State(
        create_window(options),
        create_fonts(options["font"]),
        options,
        {},
        False,
        "welcome",
        [],
        player,
        tiles,
        [],
        [],
        [],
        1 / 500,
        1 / 500,
        -1,
        0,
        4,
        4,
        Interval(options["tile"]["spawn_interval_base"], 1 / 500),
        (options["tile"]["spawn_interval_min"] - options["tile"]["spawn_interval_base"])
        / math.log(options["tile"]["spawn_interval_time"] + 1, 10),
        RandomInterval(
            options["coin"]["spawn_interval_base"],
            options["coin"]["spawn_interval_variance"],
            1 / 500,
        ),
        Interval(options["game"]["fps"]["refresh"], 1 / 500),
        500,
        ToggleKey(),
        True,
    )

    last_time = time.time()

    while state.playing:

        state.delta = time.time() - last_time
        if state.delta <= 0:
            state.delta = 1 / 500
        last_time = time.time()

        state.keys_down = pygame.key.get_pressed()

        state.win.fill(state.options["colors"]["background"])

        if state.screen == "welcome":
            draw_welcome(state)
        elif state.screen == "game":
            draw_game(state)
        elif state.screen == "instructions":
            pass

        pygame.display.update()

        # Goes at end b/c program could only end from here
        handle_events(state)


if __name__ == "__main__":
    main()
