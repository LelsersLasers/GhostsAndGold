# GhostJump
Some sort of game in pygame


## Stuff

### Format

python -m black --line-length 100 main.py

### Check (for 'compile time' errors)

python -m mypy main.py


## Modes

- Green
    - Passive:
        - increased drop chance from chests, increased chests
    - Active:
        - Blink
- Blue
    - Passive:
        - Tiles fall slower
    - Active:
        - Shield for 1 sec
        - If tile falls on it, it breaks
            - Pops chest


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