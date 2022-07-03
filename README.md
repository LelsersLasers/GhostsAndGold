# GhostJump
Some sort of game in pygame


## Stuff

### Format

python -m black --line-length 100 main.py

### Check (for 'compile time' errors)

python -m mypy main.py



## TODO

### Bugs
- Directional check sometimes sends sideways to top?

### Main

- On chest proc, "throw" 1-3 coins
- Use random interval for chest spawn?

- 4 different 'colors'
- art, animations, particles
- chests/power ups?

### Cleaning

- Better flow through player.status == alive


### Organization

- Play with Class.var (static variables)
- Multi class inheritance
- Setup like GGEZ
    - State/controller with a update and render method
    - State.update(), state.draw() instead of update(state), draw(state)