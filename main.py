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
            (options["window_width"] - options["player_w"]) / 2,
            (options["window_height"] - options["player_h"]) / 2,
        )
        super().__init__(pt, options["player_w"], options["player_h"], "#A3BE8C")  # TODO: color

        self.speed: float = options["player_speed"]
        self.jump_vel: float = options["player_jump_vel"]
        self.gravity: float = options["player_gravity"]
        self.move_vec: Vector = Vector(0, 0)

        self.jumps = 1

        self.space_tk = ToggleKey(True)
        self.p_tk = ToggleKey()

    def update(self, keys_down: list[bool], tiles: list[Tile], delta: float) -> None:
        if keys_down[pygame.K_a]:
            self.move_vec.x = -self.speed
        elif keys_down[pygame.K_d]:
            self.move_vec.x = self.speed
        else:
            self.move_vec.x = 0

        self.move_vec.y += self.gravity * delta
        if self.space_tk.down(keys_down[pygame.K_SPACE]) and self.jumps < 2:
            self.move_vec.y = -self.jump_vel
            self.jumps += 1

        self.pt.apply(self.move_vec.scalar(delta))
        current_self: Player = copy.deepcopy(self)  # TODO: not sure if the copy is needed

        for tile in tiles:
            collision = tile.directional_collide(current_self)
            if collision == "bottom":
                self.color = "#BF616A"
                self.pt.y = tile.pt.y - self.h
            elif collision == "top":
                self.pt.y = tile.pt.y - self.h
                self.move_vec.y = 0
                self.jumps = 0
                self.space_tk.down(False)
            elif collision == "left":
                self.pt.x = tile.pt.x - self.w
            elif collision == "right":
                self.pt.x = tile.pt.x + tile.w


class Tile(Hitbox):
    def __init__(self, pt: Vector, options: dict[str, Any], falling: bool = True):
        super().__init__(pt, options["tile_w"], options["tile_w"], "#5E81AC")  # TODO: color
        self.falling = falling
        self.fall_speed = options["tile_fall_speed"]

        side_len = self.w - 4
        self.side_hbs: dict[str, Hitbox] = {
            "top": Hitbox(Vector(self.pt.x + 2, self.pt.y), side_len, 2, "#BF616A"),
            "bottom": Hitbox(Vector(self.pt.x + 2, self.pt.y + self.h - 2), side_len, 2, "#BF616A"),
            "left": Hitbox(Vector(self.pt.x, self.pt.y + 2), 2, side_len, "#BF616A"),
            "right": Hitbox(Vector(self.pt.x + self.w - 2, self.pt.y + 2), 2, side_len, "#BF616A"),
        }

    def update(self, tiles: list[Tile], delta: float) -> None:
        if self.falling:
            self.fall(self.fall_speed * delta)
            for tile in tiles:
                if tile != self and self.collide(tile):
                    self.falling = False
                    self.pt.y = tile.pt.y - self.h

    def fall(self, dist: float) -> None:
        self.pt.y += dist
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
    def __init__(self, pt: Vector, options: dict[str, Any]):
        super().__init__(pt, options, False)
        self.color = "#88C0D0"


def read_options() -> dict:
    with open("options.json", "r") as f:
        return json.load(f)


def create_window(width, height, title) -> pygame.surface.Surface:
    pygame.init()
    win = pygame.display.set_mode((width, height), pygame.SCALED)
    pygame.display.set_caption(title)  # TODO: icon
    return win


def handle_events(screen: str, keys_down: list[bool]) -> str:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            quit()

    if keys_down[pygame.K_ESCAPE]:
        pygame.quit()
        quit()
    elif keys_down[pygame.K_SPACE]:
        return "game"
    elif keys_down[pygame.K_i]:
        return "instructions"

    return screen


def draw_welcome(
    win: pygame.surface.Surface, fonts: dict[str, pygame.font.Font], options: dict[str, Any]
) -> None:
    surf_title = fonts["h1"].render(options["window_title"], True, options["text_color"])
    win.blit(
        surf_title, ((win.get_width() - surf_title.get_width()) / 2, options["welcome_title_y"])
    )

    surf_start = fonts["h2"].render(options["welcome_start_text"], True, options["text_color"])
    win.blit(
        surf_start, ((win.get_width() - surf_start.get_width()) / 2, options["welcome_start_y"])
    )

    surf_instructions = fonts["h2"].render(
        options["welcome_instructions_text"], True, options["text_color"]
    )
    win.blit(
        surf_instructions,
        ((win.get_width() - surf_instructions.get_width()) / 2, options["welcome_instructions_y"]),
    )


def count_full_rows(tiles: list[Tile], options: dict[str, Any]) -> int:
    tile_ys: dict[float, int] = {}
    for tile in tiles:
        try:
            tile_ys[tile.pt.y] += 1
        except KeyError:
            tile_ys[tile.pt.y] = 1

    count = 0
    for value in tile_ys.values():
        if value == options["tile_columns"]:
            count += 1

    return count


def calc_drop_chances(tiles: list[Tile], options: dict[str, Any]) -> list[float]:
    top_tile: dict[float, float] = {} # dict[X, Y]
    for tile in tiles:
        if type(tile) != EdgeTile and not tile.falling:
            try:
                if top_tile[tile.pt.x] > tile.pt.y:
                    top_tile[tile.pt.x] = tile.pt.y
            except KeyError:
                top_tile[tile.pt.x] = tile.pt.y

    # min:max -> 10:90
    max_value: float = max(top_tile.values())
    min_value: float = min(top_tile.values())

    old_range = max_value - min_value
    new_range = options["tile_spawn_scale_max"] - options["tile_spawn_scale_min"]  

    drop_chances: list[float] = []
    for value in top_tile.values():
        try:
            new_value = (((value - min_value) * new_range) / old_range) + options["tile_spawn_scale_min"]  
        except ZeroDivisionError:
            new_value = 10
        drop_chances.append(new_value)

    return drop_chances


def draw_game(
    win: pygame.surface.Surface,
    keys_down: list[bool],
    delta: float,
    ticks: float,
    player: Player,
    tiles: list[Tile],
    tile_spawn: Interval,
    full_rows: int,
    options: dict[str, Any],
) -> int:

    for tile in tiles:
        tile.update(tiles, delta)
        tile.draw(win)

    count = count_full_rows(tiles, options)
    if count > full_rows:
        for tile in tiles:
            tile.fall(options["tile_w"])
        player.pt.y += options["tile_w"]
        tiles.append(EdgeTile(Vector(0, options["tile_top_y"]), options))
        tiles.append(
            EdgeTile(
                Vector(options["window_width"] - options["tile_w"], options["tile_top_y"]), options
            )
        )
        full_rows += 1

    if tile_spawn.update(ticks):
        drop_chances = calc_drop_chances(tiles, options)
        drop_chance_list: list[float] = []
        for i in range(len(options["tile_spawn_xs"])):
            drop_chance_list += [options["tile_spawn_xs"][i]] * int(drop_chances[i])

        tiles.append(
            Tile(Vector(random.choice(drop_chance_list), options["tile_spawn_y"]), options)
        )

    player.update(keys_down, tiles, delta)
    player.draw(win)

    return full_rows


def main():

    options = read_options()

    win = create_window(options["window_width"], options["window_height"], options["window_title"])

    fonts = {
        "h1": pygame.font.Font(options["font_name"], options["h1_size"]),
        "h2": pygame.font.Font(options["font_name"], options["h2_size"]),
    }

    playing = True
    screen = "welcome"

    player = Player(options)
    tiles: list[Tile] = []
    tile_y = options["tile_base_y"]

    for i in range(options["tile_columns"] - 2):
        tiles.append(Tile(Vector((i + 1) * options["tile_w"], tile_y), options, False))

    while tile_y > -options["tile_w"]:
        tiles.append(EdgeTile(Vector(0, tile_y), options))
        tiles.append(EdgeTile(Vector(options["window_width"] - options["tile_w"], tile_y), options))
        options["tile_top_y"] = tile_y # TODO: change - modifying options
        tile_y -= options["tile_w"]

    last_time = time.time()
    ticks = 1 / 500

    full_rows = 1

    tile_spawn = Interval(options["tile_spawn_interval"], ticks)

    while playing:

        delta = time.time() - last_time
        if delta <= 0:
            delta = 1 / 500
        last_time = time.time()

        ticks += delta

        keys_down = pygame.key.get_pressed()

        screen = handle_events(screen, keys_down)

        win.fill(options["background_color"])

        if screen == "welcome":
            draw_welcome(win, fonts, options)
        elif screen == "game":
            full_rows = draw_game(
                win, keys_down, delta, ticks, player, tiles, tile_spawn, full_rows, options
            )
        elif screen == "instructions":
            pass

        pygame.display.update()

        # print("Delta: %1.3f\tFPS: %4.2f" % (delta, 1 / delta))


if __name__ == "__main__":
    main()
