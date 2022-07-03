# GhostJump
Some sort of game in pygame


## Stuff

### Format

python -m black --line-length 100 main.py

### Check (for 'compile time' errors)

python -m mypy main.py


## Modes

- White
    - default
    - Passive:
        - Increased jump height
    - Active
        - Teleport to top of screen
        - Medium CD
- Red
    - Passive:
        - Increased speed (left right)
    - Active:
        - Dash direction moving
        - Lowish CD
- Green
    - Passive:
        - Tiles fall slower
    - Active:
        - shield that breaks falling tile
            - will pop a chest
        - long CD
- Blue
    - Passive:
        - Increased coin pop chance
    - Active:
        - Drop coin at random location


## TODO

### Bugs
- Directional check sometimes sends sideways to top?

### Main

- Modes:
    - Actives?
    - Is 4 too many?
    - Remove all together (replace with just 1 active)
- Polish
    - art, animations, particles, lights, etc

### Cleaning

- Better flow/care with:
    - Player.status == alive
    - Fall.falling
- Types
    - All functions have return type
    - All parameters have type
    - All member variables have type
- When using options in class vs member variables


### Organization

- Play with Class.var (static variables)
- Multi class inheritance
- Setup like GGEZ
    - State/controller with a update and render method
    - State.update(), state.draw() instead of update(state), draw(state)