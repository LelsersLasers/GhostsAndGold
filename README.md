# GhostJump

Some sort of game in pygame


## Download

Download latest working version (windows/.exe):
- https://github.com/LelsersLasers/GhostJump/raw/main/dist/GhostJumpEXE.zip
- Comes pre-packaged with the correct version of python
Download latest working version (all OSes/python):
- https://github.com/LelsersLasers/GhostJump/raw/main/dist/GhostJumpPython.zip
- Note: this version requires python to be installed

## Self notes

### Format

python -m black --line-length 100 main.py

### Check (for 'compile time' errors)

python -m mypy main.py

### Package to .exe

C:\Python39\Scripts\pyinstaller.exe --onefile --noconsole main.py

## TODO

### Bugs

- Directional check sometimes sends sideways to top?
- Directional check sometimes misses??

### Main

- "Down thrust"
- PERFORMANCE
    - Once X rows of full tiles, remove a row
        - Remove at 1 higher than current to avoid showing edge tile bottom
    - Replace pygame.draw with blit?
    - I loop through the tiles like a billion times
- Shield has set time?
    - Or 1 time block?
- Instructions screen
- Polish
    - art, animations, particles, lights, etc

### Cleaning

- Scroll + remove row
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