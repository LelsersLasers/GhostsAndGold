from __future__ import annotations  # for type hints
from typing import Any

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


class Player(Hitbox):
    def __init__(self, options: dict[str, Any]):
        pt = Vector(
            (options["window"]["width"] - options["player"]["w"]) / 2,
            (options["window"]["height"] - options["player"]["h"]) / 2,
        )
        super().__init__(
            pt, options["player"]["w"], options["player"]["h"], "#A3BE8C"
        )  # TODO: color

        self.speed: float = options["player"]["speed"]
        self.jump_vel: float = options["player"]["jump_vel"]
        self.gravity: float = options["player"]["gravity"]
        self.move_vec: Vector = Vector(0, 0)

        self.jumps = 1

        self.space_tk = ToggleKey(True)
        self.p_tk = ToggleKey()

        self.status = "alive"

    def key_input(self, keys_down: list[bool]) -> None:
        if keys_down[pygame.K_a]:
            self.move_vec.x = -self.speed
        elif keys_down[pygame.K_d]:
            self.move_vec.x = self.speed
        else:
            self.move_vec.x = 0

        if self.space_tk.down(keys_down[pygame.K_SPACE]) and self.jumps < 2:
            self.move_vec.y = -self.jump_vel
            self.jumps += 1

    def move(self, delta: float) -> None:
        self.move_vec.y += self.gravity * delta
        self.pt.apply(self.move_vec.scalar(delta))

    def check_tile_collision(self, tiles: list[Tile]) -> None:
        current_self: Player = copy.deepcopy(self)  # TODO: not sure if the copy is needed

        for tile in tiles:
            collision = tile.directional_collide(current_self)
            if collision == "bottom":
                self.color = "#BF616A"
                self.status = "dead"
                self.move_vec.x = 0
            elif collision == "top":
                self.pt.y = tile.pt.y - self.h
                self.move_vec.y = 0
                self.jumps = 0
                self.space_tk.down(False)
            elif collision == "left":
                self.pt.x = tile.pt.x - self.w
            elif collision == "right":
                self.pt.x = tile.pt.x + tile.w

    def update(self, state: dict[str, Any]) -> None:
        self.key_input(state["keys_down"])
        self.move(state["delta"])
        self.check_tile_collision(state["tiles"])


class Fall(Hitbox):
    def __init__(
        self, pt: Vector, w: float, h: float, color: str, fall_speed: float, falling: bool
    ):
        super().__init__(pt, w, h, color)
        self.fall_speed = fall_speed
        self.falling = falling

    def fall(self, dist: float) -> None:
        self.pt.y += dist


class Tile(Fall):
    def __init__(self, pt: Vector, tile_options: dict[str, Any], falling: bool = True):
        super().__init__(
            pt, tile_options["w"], tile_options["w"], "#5E81AC", tile_options["fall_speed"], falling
        )  # TODO: color

        side_len = self.w - 4
        self.side_hbs: dict[str, Hitbox] = {
            "top": Hitbox(Vector(self.pt.x + 2, self.pt.y), side_len, 2, "#BF616A"),
            "bottom": Hitbox(Vector(self.pt.x + 2, self.pt.y + self.h - 2), side_len, 2, "#BF616A"),
            "left": Hitbox(Vector(self.pt.x, self.pt.y + 2), 2, side_len, "#BF616A"),
            "right": Hitbox(Vector(self.pt.x + self.w - 2, self.pt.y + 2), 2, side_len, "#BF616A"),
        }

    def update(self, state: dict[str, Any]) -> None:
        if self.falling:
            self.fall(self.fall_speed * state["delta"])
            for tile in state["tiles"]:
                if tile != self and self.collide(tile):
                    self.falling = False
                    self.pt.y = tile.pt.y - self.h

    def fall(self, dist: float) -> None:
        super().fall(dist)
        for value in self.side_hbs.values():
            value.pt.y += dist

    def directional_collide(self, player: Player) -> str:
        if self.collide(player):
            if player.collide(self.side_hbs["top"]):
                return "top"
            elif player.collide(self.side_hbs["bottom"]):
                return "bottom"
            elif player.collide(self.side_hbs["left"]):
                return "left"
            elif player.collide(self.side_hbs["right"]):
                return "right"
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

    def update(self, state: dict[str, Any]):
        if self.falling:
            self.fall(self.fall_speed * state["delta"])
            for tile in state["tiles"]:
                collision = tile.directional_collide(self)
                if collision == "bottom":
                    state["coins"].remove(self)
                    break
                elif collision == "top":
                    self.falling = False
                    break


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


def handle_events(state: dict[str, Any]) -> None:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            quit()

    if state["screen"] == "welcome":
        if state["keys_down"][pygame.K_SPACE]:
            state["tile_spawn"].reset(state["ticks"])
            state["coin_spawn"].reset(state["ticks"])
            state["screen"] = "game"
        elif state["keys_down"][pygame.K_i]:
            state["screen"] = "instructions"
        elif state["keys_down"][pygame.K_ESCAPE]:
            pygame.quit()
            quit()
    elif state["screen"] == "instructions":
        if state["keys_down"][pygame.K_ESCAPE]:
            state["screen"] = "welcome"


def draw_welcome(state: dict[str, Any]) -> None:
    surf_title = state["fonts"]["h1"].render(
        state["options"]["title"], True, state["options"]["colors"]["text"]
    )
    state["win"].blit(
        surf_title,
        (
            (state["win"].get_width() - surf_title.get_width()) / 2,
            state["options"]["welcome"]["title"]["y"],
        ),
    )

    surf_start = state["fonts"]["h3"].render(
        state["options"]["welcome"]["start"]["text"], True, state["options"]["colors"]["text"]
    )
    state["win"].blit(
        surf_start,
        (
            (state["win"].get_width() - surf_start.get_width()) / 2,
            state["options"]["welcome"]["start"]["y"],
        ),
    )

    surf_instructions = state["fonts"]["h4"].render(
        state["options"]["welcome"]["instructions"]["text"],
        True,
        state["options"]["colors"]["text"],
    )
    state["win"].blit(
        surf_instructions,
        (
            (state["win"].get_width() - surf_instructions.get_width()) / 2,
            state["options"]["welcome"]["instructions"]["y"],
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


def draw_death(state: dict[str, Any]) -> None:
    darken_rect = pygame.Surface(
        (state["win"].get_width(), state["win"].get_height()), pygame.SRCALPHA
    )
    darken_rect.fill((0, 0, 0, 10))
    state["win"].blit(darken_rect, (0, 0))

    surf_title = state["fonts"]["h2"].render(
        state["options"]["death"]["title"]["text"], True, state["options"]["colors"]["text"]
    )
    state["win"].blit(
        surf_title,
        (
            (state["win"].get_width() - surf_title.get_width()) / 2,
            state["options"]["death"]["title"]["y"],
        ),
    )

    surf_restart = state["fonts"]["h3"].render(
        state["options"]["death"]["restart"]["text"], True, state["options"]["colors"]["text"]
    )
    state["win"].blit(
        surf_restart,
        (
            (state["win"].get_width() - surf_restart.get_width()) / 2,
            state["options"]["death"]["restart"]["y"],
        ),
    )


def draw_game(state: dict[str, Any]) -> None:

    for tile in state["tiles"]:
        tile.update(state)
        tile.draw(state["win"])

    for coin in state["coins"]:
        coin.update(state)
        coin.draw(state["win"])

    count = count_full_rows(state["tiles"], state["options"]["tile"]["columns"])
    if count > state["full_rows"]:
        state["tiles"].append(
            EdgeTile(
                Vector(0, state["options"]["tile"]["top_y"] - state["scrolling"]),
                state["options"]["tile"],
            )
        )
        state["tiles"].append(
            EdgeTile(
                Vector(
                    state["options"]["window"]["width"] - state["options"]["tile"]["w"],
                    state["options"]["tile"]["top_y"] - state["scrolling"],
                ),
                state["options"]["tile"],
            )
        )
        state["full_rows"] += 1
        state["scrolling"] += state["options"]["tile"]["w"]

    if state["scrolling"] > 0:
        scroll_dist = state["delta"] * state["options"]["scroll_speed"]
        state["scrolling"] -= scroll_dist
        for tile in state["tiles"] + state["coins"]:
            tile.fall(scroll_dist)
        state["player"].pt.y += scroll_dist

    if state["tile_spawn"].update(state["ticks"]):
        drop_chances = calc_drop_chances(state["tiles"], state["options"])
        drop_chance_list: list[float] = []
        for i in range(len(state["options"]["tile"]["spawn_xs"])):
            drop_chance_list += [state["options"]["tile"]["spawn_xs"][i]] * drop_chances[i]

        state["tiles"].append(
            Tile(
                Vector(random.choice(drop_chance_list), state["options"]["tile"]["spawn_y"]),
                state["options"]["tile"],
            )
        )

    if state["coin_spawn"].update(state["ticks"]):
        state["coins"].append(
            Coin(
                Vector(
                    random.uniform(
                        state["options"]["tile"]["w"],
                        state["options"]["window"]["width"]
                        - state["options"]["tile"]["w"]
                        - state["options"]["coin"]["w"],
                    ),
                    state["options"]["coin"]["spawn_y"],
                ),
                state["options"]["coin"],
            )
        )
        state["coin_spawn"].period = state["options"]["coin"][
            "spawn_interval_base"
        ] + random.uniform(
            -state["options"]["coin"]["spawn_interval_variance"],
            state["options"]["coin"]["spawn_interval_variance"],
        )

    if state["player"].status == "alive":
        state["player"].update(state)
    state["player"].draw(state["win"])

    if state["player"].status == "dead":
        draw_death(state)
        if state["keys_down"][pygame.K_r]:
            player, tiles = setup(state["options"])
            state["player"] = player
            state["tiles"] = tiles
            state["coins"] = []
            state["scrolling"] = 0
            state["full_rows"] = 1
            state["screen"] = "welcome"


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

    state = {
        "win": create_window(options),
        "fonts": create_fonts(options["font"]),
        "options": options,
        "keys_down": [],
        "player": player,
        "tiles": tiles,
        "coins": [],
        "delta": 1 / 500,
        "ticks": 1 / 500,
        "scrolling": 0,
        "full_rows": 1,
        "tile_spawn": Interval(options["tile"]["spawn_interval"], 1 / 500),
        "coin_spawn": Interval(options["coin"]["spawn_interval_base"], 1 / 500),
        "screen": "welcome",
    }

    last_time = time.time()
    playing = True

    while playing:

        state["delta"] = time.time() - last_time
        if state["delta"] <= 0:
            state["delta"] = 1 / 500
        last_time = time.time()
        state["ticks"] += state["delta"]

        state["keys_down"] = pygame.key.get_pressed()

        handle_events(state)

        state["win"].fill(state["options"]["colors"]["background"])

        if state["screen"] == "welcome":
            draw_welcome(state)
        elif state["screen"] == "game":
            draw_game(state)
        elif state["screen"] == "instructions":
            pass

        pygame.display.update()


if __name__ == "__main__":
    main()
