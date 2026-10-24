# 3D models

Ready-made low-poly models by [Kenney](https://kenney.nl), licence CC0 1.0 (public domain, see `License.txt` in each folder). Used as they are, except one change:

- `vehicles/Textures/colormap.png`: the green swatches are recoloured to mining yellow, so the tractor reads as a loader (and the garbage truck as a haul truck).

| File | Kit | In the scene |
|---|---|---|
| `vehicles/garbage-truck.glb` | Car Kit | not shown: the Unity scene builder falls back to it if `poly/dump-truck.glb` is missing |
| `vehicles/tractor-shovel.glb` | Car Kit | loader on the ore stockpile |
| `industrial/building-r.glb` | City Kit (Industrial) 2.0 | copper concentrate shed |
| `industrial/shipping-container-a.glb` | City Kit (Industrial) 2.0 | concentrate containers |
| `industrial/detail-tank-large.glb` | City Kit (Industrial) 2.0 | flotation reagent tanks |
| `industrial/building-j.glb` | City Kit (Industrial) 2.0 | haul truck workshop |
| `industrial/building-e.glb` | City Kit (Industrial) 2.0 | admin building |
| `industrial/building-c.glb` | City Kit (Industrial) 2.0 | boiler house |
| `industrial/water-tower.glb` | City Kit (Industrial) 2.0 | water tower |
| `factory/hopper-high-round.glb` | Factory Kit 3.0 | ore hopper of the crusher |

Models by other authors, in `poly/` (sources and licences in [poly/CREDITS.md](poly/CREDITS.md); the three CC BY 3.0 models require the attribution kept there and in SUBMISSION.md):

| File | Model, author, licence | In the scene (3D page and Unity) |
|---|---|---|
| `poly/dump-truck.glb` | Dump truck, jeremy, CC BY 3.0 | haul trucks on the pit roads and at the workshop; the ore heap on the body is a box shown only on the way up |
| `poly/bulldozer.glb` | Bulldozer, Poly by Google, CC BY 3.0 | dozers in the pit and on the tailings dam |
| `poly/water-truck.glb` | Truck Tank, KolosStudios, CC BY 3.0 | water truck for dust suppression on the haul road |
| `poly/transmission-tower.glb` | Transmission Tower, iPoly3D, CC0 | towers of the power lines |
| `poly/silos.glb` | Silo Model, MaverickFX, CC0 | lime and reagent silos of the plant |

The mine-specific equipment (pit benches, shovels, crusher, grinding lines, flotation cells, thickener, tanks, pond) is built in `app.js` and the same way in the Unity scene builder, because its shape follows the twins' data. Each grinding line is a SAG mill and a ball mill with conical heads, trunnions on bearing pedestals, girth gear, pinion, gearbox and motor, and a hydrocyclone cluster between them: no open-licence model of these exists, and the drums turn with the feed.
