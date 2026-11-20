# Ferry's Sandwiches

Catch the falling ingredients on Ferry's plate and build the order in the right
order: bread, lettuce, ham, cheese, cucumber, tomato, bread on top. Avoid the junk!

## Run
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/python main.py

(or just `pip install -r requirements.txt` and `python main.py` if you don't use a venv)

## Controls
- Move: Left/Right arrows or A/D, or move the mouse / touch the screen
- Pause: P or Esc (or the II button)
- Menus: arrow keys + Enter, or the mouse
- Music and sound volume: Settings on the title screen

## Rules
- Catch the item highlighted on the ORDER ticket. A wrong (but good) item bounces off and breaks your combo.
- Junk (sock, rotten egg, coin, sponge, rotten banana): -5 seconds, -10 points.
- 3 correct catches in a row: +2s. 6 in a row: +3s and triple points.
- Finished sandwich: +50 points and +5s. Build 6 sandwiches before the 2:00 timer ends to win.
- Items fall faster after every sandwich; junk starts appearing after the first one.

## Customizing
- Tweak numbers at the top of `main.py` (time, targets, penalties, scoring).
- Background music and all sound effects are generated in `sound_synth.py`
  (`build_music` is the lo-fi loop: tempo, chords and drum pattern live there).
- Ferry's original drawings are in `assets/source/` (1545x2000 PNG):
  the empty tray, each sandwich stage, and the happy / confused faces.
- The in-game sprites `assets/ferry/ferry_<plate>_<mood>.png` (276x360) are built from
  those drawings by `tools/build_sprites.py` (needs Pillow: `pip install pillow`).
  Plate states: empty, bread, salad, ham, cheese, cucumber, tomato, breadontop;
  moods: neutral, happy, confused. Edit a drawing in `assets/source/` and re-run the script.
- Item icons live in `assets/items/`, the background in `assets/bg/`, and the menu/ticket
  pieces (Cozy UI Pack by dobo_ui) in `assets/ui/`; `nine_slice()` in `main.py` stretches them.
