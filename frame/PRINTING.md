# Film Frame stand: print notes

A standing frame for a **Kindle Paperwhite 4 (10th gen, 2018, model PQ94WIF)**. It hides the Kindle's black front except a thin line around the image, leans back 10° on two fins, and leaves room underneath for the charging cable.

## Pick a version

| Version | Print | Looks like |
|---|---|---|
| Classic | `front-classic` + `back` | wood frame, 2.5 mm black line around the photo |
| Mat | `front-mat` + `mat` + `back` | wood frame, paper-coloured passe-partout around the photo |

STL and 3MF files are equivalent (millimetres). Each part comes already laid flat in its print orientation. Print **one part per plate**: front and back are each about 152 × 203 mm, so they need a 256 × 256 mm bed (or 250 × 210).

## Settings

- **Frame (front, back):** wood-fill PLA, light ("wood"/"birch") or dark ("walnut"). A 0.6 mm nozzle is safest with wood fill; 0.4 works. Plain PLA in a wood colour also works.
- **Mat:** matte white or cream PLA, 0.2 mm layers (6 layers).
- 0.2 mm layers, 3 walls, 15% gyroid infill, **no supports, no brim**.
- The front prints **face down**, so the bed surface becomes the visible face. A textured PEI sheet gives a soft matte finish; a smooth sheet gives a satin one. The engraved `>` `<` eyes are bridged at 0.8 mm; let the bed cool before removing the part.
- Back: prints inner side down with the two kickstand fins pointing up.
- Approximate filament: front 35 g, back 41 g, mat 4 g.

## Hardware and assembly

- 4 × M3 × 12 countersunk screws (they self-tap into the 2.5 mm pilot holes), or 3.0 × 12 mm plastic/wood screws.
- Optional: small felt or silicone pads on the back plate if the Kindle rattles. The pocket is 117.5 × 167.8 × 8.5 mm for a 116.7 × 167 × 8.18 mm Kindle.

1. Lay the front face down. For the mat version, drop the mat into its recess first.
2. Put the Kindle in screen down, bottom edge (USB port) toward the legs.
3. Plug the micro-USB cable in. It runs down into the room between the middle legs and out through the notch in the back plate. A 90° micro-USB plug pointing down is neatest; a straight plug fits (32 mm of room).
4. Put the back on and screw it down. Don't overtighten: the screws only need to hold the Kindle against the front.

The power button (bottom edge, about 70 mm from the left) stays reachable from below through the opening between the middle legs.

## Where the numbers come from

- Kindle body: Amazon's spec (167 × 116 × 8.18 mm) and a measured, public-domain STEP model (Printables #1061750, 116.7 mm wide).
- Screen image: 90.6 × 122.4 mm (E Ink 6" 1072 × 1448 panel datasheets), centred left-right. Its bottom edge sits 24.4 mm above the Kindle's bottom edge (from the STEP model).
- Micro-USB at 46.35 mm and power button at 70.35 mm from the Kindle's left edge (STEP model).

Want to check the window before printing it all? In the slicer, stop the front after 3 mm (about 15 minutes), lay it over the Kindle, and look at the black line. Every number lives at the top of `build_frame.py`; rebuild with `blender -b -P build_frame.py -- out/`.
