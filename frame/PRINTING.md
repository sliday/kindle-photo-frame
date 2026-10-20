# Film Frame stand: print notes

A standing frame for a **Kindle Paperwhite 4 (10th gen, 2018, model PQ94WIF)**, in dark walnut. It hides the Kindle's black front except a thin black line around the image, leans back 10° on two fins, and hides the charger: the cable runs down inside one leg and leaves through the back of its foot.

![front](print/render-walnut.png)

## What to print

| Part | File | Print |
|---|---|---|
| Front | `front-classic` (STL or 3MF) | face down |
| Back | `back` | inner side down, kickstand fins pointing up |

Optional instead of the black line: `front-mat` plus `mat`, a paper-coloured passe-partout (`render-walnut-mat.png`).

STL and 3MF files are equivalent (millimetres), and each is laid flat in its print orientation. Print **one part per plate**. The front is 151.5 × 216.6 mm and the back 151.5 × 214.9 mm, so they need a 256 × 256 mm bed, or a 250 × 210 bed with the part turned 90°.

## Settings

- **Filament:** dark walnut wood-fill PLA, or plain PLA in walnut brown. A 0.6 mm nozzle is safest with wood fill; 0.4 works.
- 0.2 mm layers, 3 walls, 15% gyroid infill, **no supports, no brim**.
- The front prints face down, so the bed surface becomes the visible face: textured PEI gives a soft matte finish, smooth PEI a satin one. The engraved `>` `<` eyes are bridged at 0.8 mm.
- The back prints inner side down, with the fins and the cable slot facing up.
- Filament: about 39 g for the front and 42 g for the back (4 g for the optional mat).
- Run `check_print.py` (below) after any change: every part should report watertight, one body.

## Hardware

- 4 × M3 × 12 countersunk screws (they self-tap into the 2.5 mm pilot holes), or 3.0 × 12 mm plastic or wood screws.
- A micro-USB cable. A straight plug up to **25 mm** long fits; a 90° plug that points backward is neater.
- Optional: felt pads on the back plate if the Kindle rattles (the pocket is 117.5 × 167.8 × 8.5 mm for a 116.7 × 167 × 8.18 mm Kindle), and rubber feet under the legs.

## Assembly, and where the charger goes

![how the cable runs](print/render-section.png)

1. Lay the front face down. Put the Kindle in screen down, its bottom edge (with the USB port) toward the legs.
2. **Plug the cable in now**, while the back is off. The plug points down into the hollow **left inner leg** (seen from the front), which sits right under the port.
3. Run the cable down that leg's channel and out through the **small slot at the back of its foot**. Put the back on and screw it down gently; the screws only hold the Kindle against the front.
4. Stand the frame up. From the front nothing shows: the cable leaves behind the leg and lies on the shelf, out to the charger.

![cable from behind](print/render-cable.png)

**Power button:** it sits on the Kindle's bottom edge above the right inner leg. A pocket in the rail keeps the Kindle's weight off it (the button sticks out 0.6 mm). To press it, tilt the frame back and push a pen up through the 5 mm hole in the bottom of that leg. The frame never sleeps, so you'll rarely need it.

## Where the numbers come from

- Kindle body: Amazon's spec (167 × 116 × 8.18 mm) and a measured, public-domain STEP model (Printables #1061750, 116.7 mm wide).
- Screen image: 90.6 × 122.4 mm (E Ink 6" 1072 × 1448 panel datasheets), centred left-right; its bottom edge sits 24.4 mm above the Kindle's bottom edge (STEP model).
- Micro-USB at 46.35 mm and power button at 70.35 mm from the Kindle's left edge (STEP model).
- Leg layout: the micro-USB port and power button sit mirrored, 12 mm either side of the Kindle's centre, so the two inner legs sit right under them and the bot stays symmetric.
- Leg height: a 25 mm straight plug, a 10 mm cable bend and the 10° lean leave 5.9 mm above the shelf. `build_frame.py` checks this on every build and stops if a change breaks it.

Want to check the window before printing it all? In the slicer, stop the front after 3 mm (about 15 minutes), lay it over the Kindle, and look at the black line. Every number lives at the top of `build_frame.py`:

```sh
blender -b -P build_frame.py -- print --render      # rebuild parts and renders
uv run --with trimesh --with networkx --with lxml --with scipy python check_print.py print
```
