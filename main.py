from __future__ import annotations  # for type hints
from typing import Any
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

    def get_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

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
    keys_down: list[bool]
    player: Player
    tiles: list[Tile]
    coins: list[Coin]
    chests: list[Chest]
    delta: float
    ticks: float
    score: int
    scrolling: float
    full_rows: int
    tile_spawn: Interval
    coin_spawn: RandomInterval
    screen: str


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
        if state.player.alive and self.collide(state.player):
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
        self.last_dir = "right"

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

        if self.mode == "green" and self.mode_cds["green"] == 0 and keys_down[pygame.K_e]:
            if self.last_dir == "right":
                self.pt.x += self.mode_options["green"]["blink_dist"]
            elif self.last_dir == "left":
                self.pt.x -= self.mode_options["green"]["blink_dist"]
            self.mode_cds["green"] = self.mode_cds_base["green"]

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
            if collision != "none" and type(tile) == EdgeTile:
                if self.last_dir == "right":
                    self.pt.x = tile.pt.x - self.w
                elif self.last_dir == "left":
                    self.pt.x = tile.pt.x + tile.w
            elif collision == "bottom":
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

        self.key_input(state.keys_down)

        if self.pt.x < 0:
            self.pt.x = 0
        elif self.pt.x + self.w > state.win.get_width():
            self.pt.x = state.win.get_width() - self.w

        self.move(state.delta)
        self.check_tile_collision(state.tiles)


class Fall(Movable):
    def __init__(
        self, pt: Vector, w: float, h: float, color: str, fall_speed: float, falling: bool
    ):
        super().__init__(pt, w, h, color, Vector(0, fall_speed), 0)
        self.falling = falling

    def scroll(self, dist: float):
        self.pt.y += dist


class Tile(Fall):
    def __init__(self, pt: Vector, tile_options: dict[str, Any], falling: bool = True):
        super().__init__(
            pt, tile_options["w"], tile_options["w"], "#81A1C1", tile_options["fall_speed"], falling
        )  # TODO: color

        side_len = self.w - 10
        self.side_hbs: dict[str, Hitbox] = {
            "top": Hitbox(Vector(self.pt.x + 5, self.pt.y), side_len, 5, "#BF616A"),
            "bottom": Hitbox(Vector(self.pt.x + 5, self.pt.y + self.h - 5), side_len, 5, "#BF616A"),
            "left": Hitbox(Vector(self.pt.x, self.pt.y + 5), 5, side_len, "#BF616A"),
            "right": Hitbox(Vector(self.pt.x + self.w - 5, self.pt.y + 5), 5, side_len, "#BF616A"),
        }

    def update(self, state: State) -> None:
        if self.falling:
            delta = state.delta
            if state.player.mode == "blue":
                delta *= state.player.mode_options["blue"]["fall"]
            self.move(delta)
            for tile in state.tiles:
                if tile != self and self.collide(tile):
                    self.falling = False
                    self.pt.y = tile.pt.y - self.h

    def scroll(self, dist: float) -> None:
        super().scroll(dist)
        for value in self.side_hbs.values():
            value.pt.y += dist

    def move(self, delta: float) -> None:
        super().move(delta)
        for value in self.side_hbs.values():
            value.pt.apply(self.move_vec.scalar(delta))

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
        super().__init__(pt, tile_options, False)
        self.color = "#88C0D0"


class Coin(Fall):
    def __init__(self, pt: Vector, coin_options: dict[str, Any]):
        super().__init__(
            pt, coin_options["w"], coin_options["h"], "#EBCB8B", coin_options["fall_speed"], True
        )

    def update(self, state: State):
        self.move(state.delta)
        for tile in state.tiles:
            collision = tile.directional_collide(self)
            if collision == "bottom":
                state.coins.remove(self)
                return  # avoid double-removal chance
            elif collision == "top":
                self.pt.y = tile.pt.y - self.h + 1
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
    }


def handle_events(state: State) -> None:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            quit()

    if state.screen == "welcome":
        if state.keys_down[pygame.K_SPACE]:
            state.tile_spawn.reset(state.ticks)
            state.coin_spawn.reset(state.ticks)
            state.score = 0
            state.screen = "game"
        elif state.keys_down[pygame.K_i]:
            state.screen = "instructions"
        elif state.keys_down[pygame.K_ESCAPE]:
            pygame.quit()
            quit()
    elif state.screen == "instructions":
        if state.keys_down[pygame.K_ESCAPE]:
            state.screen = "welcome"


def draw_welcome(state: State) -> None:
    surf_title = state.fonts["h1"].render(
        state.options["title"], True, state.options["colors"]["text"]
    )
    state.win.blit(
        surf_title,
        (
            (state.win.get_width() - surf_title.get_width()) / 2,
            state.options["welcome"]["title"]["y"],
        ),
    )

    if state.score != -1:
        surf_score = state.fonts["h4"].render(
            state.options["welcome"]["score"]["text"] % state.score,
            True,
            state.options["colors"]["text"],
        )
        state.win.blit(
            surf_score,
            (
                (state.win.get_width() - surf_score.get_width()) / 2,
                state.options["welcome"]["score"]["y"],
            ),
        )

    surf_start = state.fonts["h3"].render(
        state.options["welcome"]["start"]["text"], True, state.options["colors"]["text"]
    )
    state.win.blit(
        surf_start,
        (
            (state.win.get_width() - surf_start.get_width()) / 2,
            state.options["welcome"]["start"]["y"],
        ),
    )

    surf_instructions = state.fonts["h4"].render(
        state.options["welcome"]["instructions"]["text"],
        True,
        state.options["colors"]["text"],
    )
    state.win.blit(
        surf_instructions,
        (
            (state.win.get_width() - surf_instructions.get_width()) / 2,
            state.options["welcome"]["instructions"]["y"],
        ),
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


def calc_drop_chances(tiles: list[Tile], options: dict[str, Any]) -> list[int]:
    top_tile: dict[float, float] = {}
    for tile in tiles:
        if type(tile) != EdgeTile:
            try:
                if top_tile[tile.pt.x] > tile.pt.y:
                    top_tile[tile.pt.x] = tile.pt.y
            except KeyError:
                top_tile[tile.pt.x] = tile.pt.y

    max_value: float = max(top_tile.values())
    min_value: float = min(top_tile.values())

    old_range = max_value - min_value
    new_range = options["tile"]["spawn_scale_max"] - options["tile"]["spawn_scale_min"]

    drop_chances: list[int] = []
    for value in top_tile.values():
        if value < 0:
            new_value = 0
        else:
            try:
                new_value = ((value - min_value) * new_range) / old_range
            except ZeroDivisionError:
                new_value = 0
            new_value += options["tile"]["spawn_scale_min"]
        drop_chances.append(int(new_value))

    return drop_chances


def draw_death(state: State) -> None:
    darken_rect = pygame.Surface((state.win.get_width(), state.win.get_height()), pygame.SRCALPHA)
    darken_rect.fill((0, 0, 0, 10))
    state.win.blit(darken_rect, (0, 0))

    surf_title = state.fonts["h2"].render(
        state.options["death"]["title"]["text"], True, state.options["colors"]["text"]
    )
    state.win.blit(
        surf_title,
        (
            (state.win.get_width() - surf_title.get_width()) / 2,
            state.options["death"]["title"]["y"],
        ),
    )

    surf_restart = state.fonts["h3"].render(
        state.options["death"]["restart"]["text"], True, state.options["colors"]["text"]
    )
    state.win.blit(
        surf_restart,
        (
            (state.win.get_width() - surf_restart.get_width()) / 2,
            state.options["death"]["restart"]["y"],
        ),
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
        state.win.blit(
            surf_cd,
            (
                text_pt.x,
                text_pt.y,
            ),
        )


def draw_game(state: State) -> None:

    # TODO: combine
    for tile in state.tiles:
        tile.update(state)
        tile.draw(state.win)

    for chest in state.chests:
        chest.update(state)
        chest.draw(state.win)

    for coin in state.coins:
        coin.update(state)
        coin.draw(state.win)

    count = count_full_rows(state.tiles, state.options["tile"]["columns"])
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
        state.full_rows += 1
        state.scrolling += state.options["tile"]["w"]

    if state.scrolling > 0:
        scroll_dist = state.delta * state.options["scroll_speed"]
        state.scrolling -= scroll_dist
        # TODO: combine
        for tile in state.tiles:
            tile.scroll(scroll_dist)
        for coin in state.coins:
            coin.scroll(scroll_dist)
        state.player.pt.y += scroll_dist

    if state.tile_spawn.update(state.ticks):
        drop_chances = calc_drop_chances(state.tiles, state.options)
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
    state.player.draw(state.win)

    surf_score = state.fonts["h4"].render(
        state.options["game"]["score"]["text"] % state.score,
        True,
        state.options["colors"]["text"],
    )
    state.win.blit(
        surf_score,
        (
            (state.win.get_width() - surf_score.get_width()) / 2,
            state.options["game"]["score"]["y"],
        ),
    )

    draw_hud(state)

    if not state.player.alive:
        draw_death(state)
        if state.keys_down[pygame.K_r]:
            state.player, state.tiles = setup(state.options)
            state.coins = []
            state.chests = []
            state.scrolling = 0
            state.full_rows = 1
            state.screen = "welcome"


def setup(options: dict[str, Any]) -> tuple[Player, list[Tile]]:
    player = Player(options)
    tiles: list[Tile] = []

    tile_y = options["tile"]["base_y"]
    for i in range(options["tile"]["columns"] - 2):
        tiles.append(Tile(Vector((i + 1) * options["tile"]["w"], tile_y), options["tile"], False))
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


def main():

    options = read_options()
    player, tiles = setup(options)

    state = State(
        create_window(options),
        create_fonts(options["font"]),
        options,
        [],
        player,
        tiles,
        [],
        [],
        1 / 500,
        1 / 500,
        -1,
        0,
        1,
        Interval(options["tile"]["spawn_interval_base"], 1 / 500),
        RandomInterval(
            options["coin"]["spawn_interval_base"],
            options["coin"]["spawn_interval_variance"],
            1 / 500,
        ),
        "welcome",
    )

    last_time = time.time()
    playing = True

    while playing:

        state.delta = time.time() - last_time
        if state.delta <= 0:
            state.delta = 1 / 500
        last_time = time.time()
        state.ticks += state.delta

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
