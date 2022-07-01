from __future__ import annotations  # for type hints
from typing import Any

import pygame  # graphics library

import math
import time
import json


class ToggleKey:
    def __init__(self):
        self.was_down = False

    def down(self, condition: bool) -> bool:
        if not self.was_down and condition:
            self.was_down = True
            return True
        elif not condition:
            self.was_down = False
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

    def check_collide(self, hb: Hitbox) -> bool:
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
        self.y_vel = 0

        self.space_tk = ToggleKey()

    def update(self, keys_down: list[bool], delta: float):
        if keys_down[pygame.K_a]:
            self.pt.x -= self.speed * delta
        if keys_down[pygame.K_d]:
            self.pt.x += self.speed * delta

        self.y_vel += self.gravity * delta

        if self.space_tk.down(keys_down[pygame.K_SPACE]):
            self.y_vel = -self.jump_vel

        self.pt.y += self.y_vel * delta



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


def draw_game(win: pygame.surface.Surface, keys_down: list[bool], delta: float, player: Player):

    player.update(keys_down, delta)
    player.draw(win)


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

    last_time = time.time()
    ticks = 0.1

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
            draw_game(win, keys_down, delta, player)
        elif screen == "instructions":
            pass

        pygame.display.update()

        print("Delta: %1.3f\tFPS: %4.2f" % (delta, 1 / delta))


if __name__ == "__main__":
    main()
