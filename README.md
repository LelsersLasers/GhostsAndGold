# GhostJump

Some sort of game in pygame


## Download

Download latest working version (windows/.exe):
- https://github.com/LelsersLasers/GhostJump/raw/main/dist/GhostJumpEXE.zip
- Comes pre-packaged with the correct version of python
- Might trigger a virus scan
    - If you can not get around the scan or are not on windows use the next link
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

- Sequnce list on keys_down
- Directional check sometimes sends sideways to top?
- Directional check sometimes misses??

### Main

- Passive, active choice
- Setup like GGEZ
    - State/controller with a update and render method
    - State.update(), state.draw() instead of update(state), draw(state)
- PERFORMANCE
    - Run State.update() in background of State.draw()
    - Replace pygame.draw with blit?
    - I loop through the tiles like a billion times
        - Use tile_map when possible
    - Edge tiles:
        - Update could be slimmer than Tile
        - Keep in seperate list/tile_map than Tiles?
            - Not needing to check if it is falling on chest/coin
            - But need to check side ways for player and coin
        - Could remove bottom row? And just modify the bottom row tiles to not fall?
- Settings screen with diffulity sliders
    - Ability/passive chooser?
    - Save highscore and settings to a different file
- Polish
    - art, animations, particles, lights, etc

### Cleaning

- Removing during iteration
- Downscroll
- Make sure tup offsets for map_dict cover all cases
- Returns, breaks, etc
- Not need to convert/pass fake tuple (r, g, b)
- Types
    - All functions have return type
    - All parameters have type
    - All member variables have type
- Options vs member variables
- Try to remove "# type: ignore"
- Sequence vs list?
- Where the key_board input is
    - Where the TKs and KeyLists are
- Where the resets, removals, etc are


### Organization

- Play with Class.var (static variables)
- Multi class inheritance