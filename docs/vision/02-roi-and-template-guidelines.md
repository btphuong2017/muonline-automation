## ROI and template guidelines

To ensure consistent and efficient detection, define **regions of interest (ROIs)** for every UI element you need to detect.  Use these guidelines when defining and using ROIs and templates:

### Defining ROIs

* **Relative coordinates** – Express ROIs relative to the top‑left corner of the game client (e.g., `left=0.05`, `top=0.04`, `width=0.15`, `height=0.08`).  This makes them resolution‑independent as long as all clients share the same resolution.  Avoid hard‑coding absolute pixel values.
* **Small and focused** – Keep ROIs as small as possible while fully containing the target element.  Smaller ROIs speed up template matching and reduce false matches from similar icons elsewhere.
* **Anchored to other UI** – When an element appears inside a dialog or popup, anchor its ROI to the dialog’s detected position rather than the entire screen.  For example, once you detect the NPC dialog, compute the Enter button ROI relative to the dialog’s top‑left corner.
* **Avoid interactive regions** – Do not include chat boxes, toolbars or dynamic 3D scenes in an ROI unless necessary.  Background movement can corrupt template matching.

### Creating templates

* **Capture from the correct resolution** – Take screenshots directly from the client resolution that the bot will run on.  Do not resize images in external editors; resizing changes anti‑aliasing and edges.
* **Trim whitespace** – Remove extra blank space around the template to improve matching accuracy.  The template should tightly bound the visible pixels of the element.
* **Multiple versions** – Some elements change colour or state (e.g., enabled/disabled buttons, helper play/pause icons, timer modes).  Create a template for each state you need to detect.
* **Naming conventions** – Name template files descriptively (e.g., `lobby_label.png`, `npc_dialog_title.png`, `enter_varka_button.png`, `helper_play_icon.png`).  Maintain a consistent directory structure, such as grouping templates by flow (lobby, NPC, popups, event map) or by type (buttons, icons, labels).
* **Store metadata** – For each template, record the target ROI and a recommended confidence threshold in a configuration file (JSON/YAML).  The detection code should read these values rather than hard‑coding them.

### Using templates

* **Initial detection vs verification** – Use template matching to propose candidate locations.  Always verify the candidate via a secondary check (hover indicator, dialog detection or a second template) before acting.
* **Confidence thresholds** – Choose conservative thresholds (e.g., 0.85–0.90) to avoid false positives.  If a match’s confidence falls below the threshold, treat it as a non‑match and either try another template or move to the next state.
* **Partial matching** – For large elements (NPCs or complex panels), break the template into smaller pieces and match each piece separately.  A successful partial match suggests the object may be present, but it must still be verified.
* **Dynamic ROIs** – For elements that may move (like NPCs), expand the ROI gradually if no match is found in the initial small ROI.  Start narrow and widen only as needed to maintain performance.

### Updating templates

* When the game client updates its UI or if you change resolution, review and update all templates and ROIs.
* Maintain a script or set of instructions for capturing new templates.  Consistency is key; take screenshots under similar lighting and settings.

Following these guidelines will help maintain a clean separation between the detection logic and the data it uses.  Agents should adjust ROIs and templates only via configuration and assets, not by modifying code logic.
