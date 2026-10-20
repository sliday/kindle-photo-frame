# Codex consult: charger connection (2026-10-20, gpt-6.1-sol, session 01a15b1a)

1. **The straight-plug claim is unreliable. A 25 mm plug leaves insufficient bend space.**  
   In `make_front()` ([line 240](../frame/build_frame.py:240)), 9.5 mm describes the cutter depth, not an enclosed tunnel. Below Z=6, the rear notch opens the path behind the frame.

   Assume the port sits at Y≈6.49, halfway through the Kindle thickness. The code supplies no port depth. With the 10° lean:

   | Plug length | Cable start above shelf | After an 8 mm bend | After a 12 mm bend |
   |---|---:|---:|---:|
   | 18 mm | 12.7 mm | 3.4 mm | −1.2 mm |
   | 25 mm | 5.8 mm | −3.5 mm | −8.1 mm |

   These heights describe the cable centreline before cable thickness. Negative values mean shelf collision. The lean hurts: the shelf rises toward the rear in frame coordinates, per `floor_z()` ([line 192](../frame/build_frame.py:192)).

   **Fix:** increase `LEG_H` from 22 to **36 mm** ([line 38](../frame/build_frame.py:38)). With a 25 mm plug, 12 mm bend radius, and 4 mm cable diameter, this leaves about **3.7 mm shelf clearance**. Measure the actual connector before release. A specified rear-facing right-angle plug offers another solution; “90° pointing down” does not define its orientation.

2. **The cable route does not read from either render.**  
   The 43.5 mm mascot opening and 33.5 mm rear notch resemble decorative leg gaps.

   **Single geometry change:** replace the broad rear notch with a **16 mm wide, bottom-open U-slot centred at X=54.75**, directly behind the USB port. Extend its top to **Z=10.5**. Change `make_back()` ([line 292](../frame/build_frame.py:292)).

   This gives the cable a distinct exit and removes the 4 mm rear lip below the port. Keep the slot through the plate thickness. Both specified print orientations remain support-free. Combine this change with the clearance fix above.

3. **Users must lift or tip the frame to grip the plug.**  
   A 10.5 × 6.5 mm overmould fits the front’s **8.5 mm actual recess depth**, with only **2 mm total depth clearance**. That does not provide finger clearance.

   The rear notch leaves only **4.8 mm** between the button centre, X=78.75, and its right edge. A fingertip can approach from below; users cannot obtain a comfortable pinch grip inside that recess.

   **Fix:** specify connection before back assembly, then lift the stand for reconnection. For easier button access, add a separate **16 mm wide bottom-open relief centred at X=78.75**, reaching **Z=10.5**, in `make_back()` line 292. The assertion at [line 68](../frame/build_frame.py:68) checks X clearance alone, not hand access.

4. **The bottom has thin sections, but the fins do not block the intended route.**  
   `make_front()` leaves a **2.4 mm front skin** across the cavity. `make_back()` leaves nominal **5 mm shoulders** beside the notch and a **4 mm high strip** between Z=6 and Z=10. Avoid levering the connector against these edges. Use **R2 internal corners** in the cavity cutter at line 240.

   The fins occupy **X=35.25–39.25** and **94.25–98.25**. They leave **55 mm clear** between them. Keep the cable inside that corridor. For strain relief, add a rounded cable retainer between the fins in `make_back()`, after their union at [line 291](../frame/build_frame.py:291).

   The rear footprint reaches **55 mm**, but the code supplies no mass, centre of gravity, or friction data. You cannot certify resistance to cable pulls. Fit nonslip feet and test a sideways pull.

   The cavity removes the rail beneath the button, so the code shows no direct button contact during insertion. Keep retainers clear of **X=75.95–81.55**.

5. **Add two connection views.**  
   `render_frame.py` models the Kindle as a plain solid, with no connector or cable ([line 157](../frame/render_frame.py:157)).

   - **Low rear three-quarter close-up:** show the inserted plug, cable exit, fins, and cable on the shelf.
   - **Side section at X=54.75:** show the port, overmould, bend radius, and minimum shelf clearance.

   Add dimensions for plug length and bend radius. Skip the exploded view for this explanation. Replace the “straight plug fits” claim in `PRINTING.md` line 30 and the “32 mm room” shorthand in `build_frame.py` line 351.

ASK: Review charging access from the code and renders without edits.  
🟩Got 🟩Had 🟩Did  
🧠 —