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

- Shield has set time?
    - Or 1 time block?
- Instructions screen
- Polish
    - art, animations, particles, lights, etc

### Cleaning

- Not need to convert to (r, g, b)
- Better flow/care with:
    - Player.status == alive
- Types
    - All functions have return type
    - All parameters have type
    - All member variables have type
- When using options in class vs member variables
- Try to remove "# type: ignore"
- Sequence vs list?
- Where the key_board input is
    - Where the TKs are
- Where the resets, removals, etc are


### Organization

- Play with Class.var (static variables)
- Multi class inheritance
- Setup like GGEZ
    - State/controller with a update and render method
    - State.update(), state.draw() instead of update(state), draw(state)