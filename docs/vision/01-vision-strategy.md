## Vision strategy

The vision layer is responsible for understanding what is on the screen by analysing image data.  It **does not** hook into the game or read memory.  Instead it captures images from the game windows and uses computer vision techniques to detect UI elements, characters and game states.  The core principles of the vision strategy are:

1. **ROI‑based detection** – Never process the entire screen when a smaller *region of interest* (ROI) will suffice.  For example, the lobby map label is always near the top‑left corner, the dungeon timer is near the bottom‑right, and helper controls are near the top‑left.  Restricting detection to ROIs improves performance and reduces false positives.

2. **Template matching instead of OCR** – Small fonts and stylised text in Mu Online are difficult to recognise reliably with OCR.  Wherever possible, prepare clear templates of UI elements (e.g., buttons, icons, labels) and use template matching (e.g., `cv2.matchTemplate`) to detect their presence.  OCR may be used as a fallback for larger or simpler text (such as timer numbers), but it should never be the sole source of truth.

3. **Multi‑signal confirmation** – Do not rely on a single visual cue to decide that a state has changed.  For example, the lobby is confirmed by the presence of the waiting room label **and** the absence of the dungeon timer and finish dialog.  Using multiple signals reduces the risk of misclassification.

4. **Partial templates and hierarchical search** – Large templates of entire objects (e.g., the whole NPC) often fail when the object is partially occluded or scaled differently.  Instead, create multiple smaller templates of distinctive parts (the NPC’s shoulder, weapon or colour patch) and search for each of them.  Start with cached points that have worked previously, then try partial templates, and fall back to coarse grid searches if needed.  Each candidate must still pass the hover indicator check before clicking.

5. **Stable screen detection** – Many actions depend on the screen being stable.  Before acting, capture the same ROI multiple times and check for similarity.  If the ROI changes (e.g., due to loading animations or map transitions), wait until it stabilises.  This reduces false negatives when the scene is still loading.

6. **Caching and learning** – When the bot successfully clicks an NPC or a button, record the relative position for that resolution.  Use these cached positions as high‑priority candidates on subsequent runs.  Always verify cached points with the hover indicator or dialog detection; stale cache entries must not be used blindly.

7. **Resolution consistency** – All templates are resolution‑dependent.  The bot assumes that every game window uses the same resolution and UI scaling.  If the resolution changes, the templates and ROIs must be updated accordingly.  Do not mix templates from different resolutions.

By following these principles, agents can build a vision module that is fast, reliable and maintainable.  The subsequent files provide more detailed guidelines on ROIs, templates and specific detection tasks.
