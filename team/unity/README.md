# team/unity — the complex in the Grafana Unity panel

The same complex as the 3D page (`team/web/`), as a Unity WebGL scene shown by the **Unity** panel of OpenEgiz inside Grafana. Every object of the scene is named after its twin (`kz.limit:mill-1`, …); the panel sends each one the twin's latest values from InfluxDB, and clicking an object puts its twin into the dashboard variable `twin`.

It is a second view, switched on and off on purpose. The stand works without it: the 3D page and its embedded copy in the dashboard «Рудник под лимитом» do not depend on Unity.

| Command | What it does |
|---|---|
| `make unity-build` | Builds the scene into `build/MineUnderLimits.{loader.js,framework.js,data,wasm}` (needs the Unity Editor, below) |
| `make unity-on` | Adds the dashboard **«Рудник под лимитом — Unity 3D»** to Grafana (from [grafana/rudnik-unity.json](grafana/rudnik-unity.json)) |
| `make unity-off` | Removes that dashboard; Grafana drops it within 10 s |

The build in `build/` and the dashboard are committed, so the scene is on after `make up` and the stand needs no Unity. The files are served by the platform's `unity` service at `http://localhost:8090/build/…`; `make smoke` checks them and the dashboard while the scene is on.

## Building

Unity builds only with an activated licence, and a free Personal licence is activated only by signing in to Unity Hub:

1. Install Unity Hub (Ubuntu):
   ```bash
   wget -qO - https://hub.unity3d.com/linux/keys/public | gpg --dearmor | sudo tee /usr/share/keyrings/Unity_Technologies_ApS.gpg > /dev/null
   sudo sh -c 'echo "deb [signed-by=/usr/share/keyrings/Unity_Technologies_ApS.gpg] https://hub.unity3d.com/linux/repos/deb stable main" > /etc/apt/sources.list.d/unityhub.list'
   sudo apt update && sudo apt install -y unityhub
   ```
2. Start `unityhub`, sign in, **Preferences → Licenses → Add → Get a free personal license**.
3. **Installs → Install Editor → Unity 6 LTS** with the module **Web Build Support**.
4. `make unity-build`, then `make unity-on`.

The build runs in batch mode: [Assets/Editor/MineSceneBuilder.cs](Assets/Editor/MineSceneBuilder.cs) generates the scene from code (the layout of `team/web/app.js`), imports the models from `team/web/models/` with glTFast (Kenney CC0 kits, and the Poly Pizza dump truck, bulldozer, water truck, lattice towers and silos, credited in [poly/CREDITS.md](../web/models/poly/CREDITS.md)), sizes each one by its own bounds (`Fit`), and writes an uncompressed WebGL build, as the panel requires. The log is in `team/unity/Logs/build.log`.

## How the data gets in

The panel runs two Flux queries (numbers; text and flags), one row per twin, and calls `SendMessage(thingId, "SetValues", json)` for every row. [TwinState](Assets/Scripts/TwinState.cs) keeps the values by feature name; small components turn them into the scene:

| Component | Shows |
|---|---|
| `TruckFleet` | haul trucks per face ∝ shovel rate / 420 t/h, loaded up, empty down |
| `FlowMarkers` | ore, slurry, water, concentrate and power flows ∝ their twin values |
| `MillDrum` | grinding lines turn with feed; grey under repair, red when tripped |
| `ScaleByFeature` | stockpile cones, process water level, pond area |
| `StateColor` | hard ore, high-density thickening, low tank, intake and substation near their limits |
| `Bottleneck` | amber pulse on the planner's bottleneck twins |
| `SkyClock` | sun and sky from the model time |
| `TwinLabel`, `TwinPicker` | labels with live values; click card and the `SelectTwin` event to Grafana |
