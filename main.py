from __future__ import annotations
from typing import Any, Union
from dataclasses import dataclass  # for struct like classes

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


@dataclass  # auto writes __init__ and __repr__
class State:
    win: pygame.surface.Surface
    fonts: dict[str, pygame.font.Font]
    options: dict[str, Any]
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
    tile_spawn: Interval
    coin_spawn: RandomInterval
    fps_draw: Interval
    display_fps: int
    esc_tk: ToggleKey


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
    def __init__(self, chest_options, color: str, bot_tile: Tile):
        super().__init__(
            Vector(
                bot_tile.pt.x + (bot_tile.w - chest_options["w"]) / 2,
                bot_tile.pt.y - chest_options["h"],
            ),
            chest_options["w"],
            chest_options["h"],
            color,
        )
        self.bot_tile = bot_tile

    def update(self, state: State) -> None:
        self.pt.y = self.bot_tile.pt.y - self.h

        for tile in state.tiles:
            collision = tile.directional_collide(self)
            if collision == "bottom":
                state.chests.remove(self)
                return
        if (state.player.alive and self.collide(state.player)) or not self.bot_tile in state.tiles:
            state.chests.remove(self)
            num_coins = random.choice(state.options["coin"]["pop"]["coin_chances"])
            if state.player.mode == "green":
                num_coins = random.choice(state.player.mode_options["green"]["coin_chances"])
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
            "#A3BE8C",
            Vector(0, 0),
            options["player"]["gravity"],
        )
        self.speed: float = options["player"]["speed"]
        self.jump_vel: float = options["player"]["jump_vel"]
        self.jumps: int = 1
        self.space_tk: ToggleKey = ToggleKey(True)
        self.alive: bool = True
        self.last_dir: str = "right"
        self.shield: float = 0

        self.modes: list[str] = ["green", "blue"]
        self.mode: str = "green"
        self.mode_options: dict[str, Any] = options["player"]["mode"]
        self.mode_cds_base: dict[str, float] = {
            "green": options["player"]["mode"]["green"]["cd"],
            "blue": options["player"]["mode"]["blue"]["cd"],
        }
        self.mode_cds: dict[str, float] = copy.deepcopy(self.mode_cds_base)

    def key_input(self, keys_down: list[bool]) -> None:
        if keys_down[pygame.K_1]:
            self.mode = "green"
        elif keys_down[pygame.K_2]:
            self.mode = "blue"

        self.move_vec.x = 0
        if keys_down[pygame.K_d] or keys_down[pygame.K_RIGHT]:
            self.move_vec.x = self.speed
            self.last_dir = "right"
        elif keys_down[pygame.K_a] or keys_down[pygame.K_LEFT]:
            self.move_vec.x = -self.speed
            self.last_dir = "left"

        if self.mode == "green" and self.mode_cds["green"] == 0 and keys_down[pygame.K_q]:
            if self.last_dir == "right":
                self.pt.x += self.mode_options["green"]["blink_dist"]
            elif self.last_dir == "left":
                self.pt.x -= self.mode_options["green"]["blink_dist"]
            self.mode_cds["green"] = self.mode_cds_base["green"]

        if self.mode == "blue" and self.mode_cds["blue"] == 0 and keys_down[pygame.K_q]:
            self.shield = self.mode_options["blue"]["shield_time"]
            self.mode_cds["blue"] = self.mode_cds_base["blue"]

        if (
            self.space_tk.down(keys_down[pygame.K_SPACE] or keys_down[pygame.K_UP])
            and self.jumps < 2
        ):
            self.move_vec.y = -self.jump_vel
            self.jumps += 1

    def check_tile_collision(self, tiles: list[Tile]) -> None:
        current_self: Player = copy.deepcopy(self)  # TODO: not sure if the copy is needed

        for tile in tiles:
            collision = tile.directional_collide(current_self)
            if collision == "bottom":
                if self.shield > 0:
                    self.shield = 0
                    tiles.remove(tile)
                else:
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

    def update(self, state: State) -> None:
        self.color = self.mode_options[self.mode]["color"]
        for key in self.mode_cds:
            self.mode_cds[key] -= state.delta
            self.mode_cds[key] = max(0, self.mode_cds[key])

        self.shield -= state.delta
        self.shield = max(0, self.shield)

        self.key_input(state.keys_down)

        if self.pt.x < state.options["tile"]["w"]:
            self.pt.x = state.options["tile"]["w"]
        elif self.pt.x + self.w + state.options["tile"]["w"] > state.win.get_width():
            self.pt.x = state.win.get_width() - self.w - state.options["tile"]["w"]

        self.move(state.delta)
        self.check_tile_collision(state.tiles)

    def draw(self, win: pygame.surface.Surface) -> None:
        super().draw(win)
        if self.shield > 0:
            pygame.draw.rect(win, self.mode_options["blue"]["shield_color"], self.get_rect(), 5)


class Fall(Movable):
    def __init__(self, pt: Vector, w: float, h: float, color: str, fall_speed: float):
        super().__init__(pt, w, h, color, Vector(0, fall_speed), 0)


class Tile(Fall):
    def __init__(
        self,
        pt: Vector,
        tile_options: dict[str, Any],
        color: str = "#81A1C1",
    ):
        super().__init__(
            pt, tile_options["w"], tile_options["w"], color, tile_options["fall_speed"]
        )  # TODO: color
        self.hbs_size: float = tile_options["hbs_size"]
        self.hbs_len: float = self.w - 2 * tile_options["hbs_size"]
        self.side_hbs: dict[str, Hitbox] = {
            "top": Hitbox(Vector(-1, -1), self.hbs_len, self.hbs_size, "#BF616A"),
            "bottom": Hitbox(Vector(-1, -1), self.hbs_len, self.hbs_size, "#BF616A"),
            "left": Hitbox(Vector(-1, -1), self.hbs_size, self.hbs_len, "#BF616A"),
            "right": Hitbox(Vector(-1, -1), self.hbs_size, self.hbs_len, "#BF616A"),
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
        delta = state.delta
        if state.player.mode == "blue":
            delta *= state.player.mode_options["blue"]["fall"]
        self.move(delta)
        self.land(state)

    def land(self, state: State) -> None:
        for tile in state.tiles:
            if tile != self and self.collide(tile):
                self.pt.y = tile.pt.y - self.h
                self.update_side_hbs()
                break

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
    def __init__(self, pt: Vector, tile_options: dict[str, Any]):
        super().__init__(pt, tile_options, "#88C0D0")
        self.move_vec.y = 0


class HeavyTile(Tile):
    def __init__(self, pt: Vector, tile_options: dict[str, Any]):
        super().__init__(pt, tile_options, "#8FBCBB")
        self.move_vec.y *= tile_options["heavy"]["fall"]

    def land(self, state: State) -> None:
        for tile in state.tiles:
            if tile != self and self.collide(tile):
                state.tiles.remove(self)
                for tile2 in state.tiles:
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
                    if state.player.shield > 0:
                        state.player.shield = 0
                    else:
                        state.player.alive = False

                state.effects.append(
                    CircleEffect(
                        self.get_center(),
                        state.options["tile"]["heavy"]["r"],
                        "#BF616A",
                        Vector(0, 0),
                        0,
                        state.options["tile"]["heavy"]["draw_time"],
                    )
                )

                break


class Coin(Fall):
    def __init__(self, pt: Vector, coin_options: dict[str, Any]):
        super().__init__(
            pt, coin_options["w"], coin_options["h"], "#EBCB8B", coin_options["fall_speed"]
        )

    def update(self, state: State):
        self.move(state.delta)
        for tile in state.tiles:
            collision = tile.directional_collide(self)
            if collision == "bottom":
                state.coins.remove(self)
                return  # avoid double-removal chance
            elif collision == "top":
                self.pt.y = tile.pt.y - self.h  # TODO: does this need a +1?
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


def read_options() -> dict:
    with open("options.json", "r") as f:
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
            quit()

    if state.screen == "welcome":
        if state.keys_down[pygame.K_SPACE]:
            reset(state)
            state.screen = "game"
        elif state.keys_down[pygame.K_i]:
            state.screen = "instructions"
        elif state.keys_down[pygame.K_ESCAPE]:
            pygame.quit()
            quit()
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


def count_full_rows(tiles: list[Tile], columns: int) -> int:
    tile_ys: dict[float, int] = {}
    for tile in tiles:
        try:
            tile_ys[tile.pt.y] += 1
        except KeyError:
            tile_ys[tile.pt.y] = 1

    count = 0
    for value in tile_ys.values():
        if value == columns:
            count += 1

    return count


def calc_drop_chances(state: State) -> list[int]:
    top_tiles: list[float] = []
    for _ in state.options["tile"]["spawn_xs"]:
        top_tiles.append(state.options["tile"]["base_y"] - state.options["tile"]["w"])
    for tile in state.tiles:
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


def draw_unpause(state: State) -> None:
    # Prob some way to do this without the '# type: ignore'
    entities: list[Hitbox] = state.tiles + state.chests + state.coins + state.effects  # type: ignore
    for e in entities:
        e.update(state)
        if e.pt.y < state.win.get_height() and e.pt.y > -e.h:
            e.draw(state.win)

    count = count_full_rows(state.tiles, state.options["tile"]["columns"])
    if count != state.full_rows:
        if count > state.full_rows:
            state.tiles.append(
                EdgeTile(
                    Vector(0, state.options["tile"]["top_y"] - state.scrolling),
                    state.options["tile"],
                )
            )
            state.tiles.append(
                EdgeTile(
                    Vector(
                        state.options["window"]["width"] - state.options["tile"]["w"],
                        state.options["tile"]["top_y"] - state.scrolling,
                    ),
                    state.options["tile"],
                )
            )

        state.scrolling += state.options["tile"]["w"] * (count - state.full_rows)
        state.full_rows = count

    # TODO: better solution than dividing by 10
    if abs(state.scrolling) > state.options["tile"]["w"] / state.options["game"]["scroll_divisor"]:
        scroll_dist = state.delta * state.options["scroll_speed"] * get_sign(state.scrolling)
        state.scrolling -= scroll_dist
        to_scroll: list[Moveable] = state.tiles + state.coins + state.effects  # type: ignore
        for ts in to_scroll:
            ts.scroll(scroll_dist)
        state.player.pt.y += scroll_dist

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
            )
        state.tiles.append(new_tile)
        chest_chance = random.random()
        if chest_chance < state.options["chest"]["spawn_chance"]:
            state.chests.append(Chest(state.options["chest"], "#B48EAD", new_tile))

        state.tile_spawn.period = max(
            state.options["tile"]["spawn_interval_base"]
            + state.options["tile"]["spawn_interval_log_rate"] * math.log(state.ticks + 1, 10),
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

    if state.player.alive:
        state.player.update(state)


def draw_pause(state: State) -> None:
    draw_darken(state)

    entities: list[Hitbox] = state.tiles + state.chests + state.coins + state.effects  # type: ignore
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
    for i in range(len(state.player.modes)):
        pt = Vector(state.options["game"]["cd_box"]["xs"][i], state.options["game"]["cd_box"]["y"])
        full_rect = (
            int(pt.x),
            int(pt.y),
            int(state.options["game"]["cd_box"]["w"]),
            int(state.options["game"]["cd_box"]["h"]),
        )
        percent = (
            state.player.mode_cds[state.player.modes[i]]
            / state.player.mode_cds_base[state.player.modes[i]]
        )
        cd_rect = (
            int(pt.x),
            int(pt.y + state.options["game"]["cd_box"]["h"] * percent),
            int(state.options["game"]["cd_box"]["w"]),
            int(state.options["game"]["cd_box"]["h"] * (1 - percent)),
        )

        pygame.draw.rect(state.win, state.options["colors"]["text"], full_rect)
        pygame.draw.rect(
            state.win, state.player.mode_options[state.player.modes[i]]["color"], cd_rect
        )
        pygame.draw.rect(state.win, state.options["colors"]["text"], full_rect, 3)

        surf_cd = state.fonts["h4"].render(
            state.options["game"]["cd_box"]["text"] % state.player.mode_cds[state.player.modes[i]],
            True,
            state.options["colors"]["background"],
        )
        text_pt = pt.add(
            Vector(
                (state.options["game"]["cd_box"]["w"] - surf_cd.get_width()) / 2,
                (state.options["game"]["cd_box"]["h"] - surf_cd.get_height()) / 2,
            )
        )
        state.win.blit(surf_cd, (text_pt.x, text_pt.y))

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

    surf_rows = state.fonts["h5"].render(
        state.options["game"]["rows"]["text"] % state.full_rows,
        True,
        state.options["colors"]["text"],
    )
    state.win.blit(
        surf_rows, ((state.options["game"]["rows"]["x"], state.options["game"]["rows"]["y"]))
    )


def draw_game(state: State) -> None:
    if not state.paused:
        draw_unpause(state)
        state.ticks += state.delta

    state.player.draw(state.win)

    draw_centered_text(
        state.win,
        state.fonts["h4"],
        state.options["game"]["score"]["text"] % state.score,
        state.options["game"]["score"]["y"],
        state.options["colors"]["text"],
    )

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
                )
            )

    tile_y += (len(tile_types) - 1) * options["tile"]["w"]
    while tile_y > -options["tile"]["w"]:
        tiles.append(EdgeTile(Vector(0, tile_y), options["tile"]))
        tiles.append(
            EdgeTile(
                Vector(options["window"]["width"] - options["tile"]["w"], tile_y), options["tile"]
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
    state.paused = False
    state.tile_spawn.reset(state.ticks)
    state.coin_spawn.reset(state.ticks)
    state.fps_draw.reset(state.ticks)
    state.score = 0


def main():

    options = read_options()
    player, tiles = setup(options)

    state = State(
        create_window(options),
        create_fonts(options["font"]),
        options,
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
        Interval(options["tile"]["spawn_interval_base"], 1 / 500),
        RandomInterval(
            options["coin"]["spawn_interval_base"],
            options["coin"]["spawn_interval_variance"],
            1 / 500,
        ),
        Interval(options["game"]["fps"]["refresh"], 1 / 500),
        500,
        ToggleKey(),
    )

    last_time = time.time()
    playing = True

    while playing:

        state.delta = time.time() - last_time
        if state.delta <= 0:
            state.delta = 1 / 500
        last_time = time.time()

        state.keys_down = pygame.key.get_pressed()

        handle_events(state)

        state.win.fill(state.options["colors"]["background"])

        if state.screen == "welcome":
            draw_welcome(state)
        elif state.screen == "game":
            draw_game(state)
        elif state.screen == "instructions":
            pass

        pygame.display.update()


if __name__ == "__main__":
    main()
