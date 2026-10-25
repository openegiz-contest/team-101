// Builds the scene of «Рудник под лимитом» from code and makes the WebGL
// build for the Grafana Unity panel:
//
//   make unity-build      (runs MineSceneBuilder.BuildWebGL in batch mode)
//
// The layout copies team/web/app.js, the 3D page: the same coordinates, the
// same twins, the same links between data and shapes. Three.js is right-handed
// and Unity left-handed, so every point goes through P(x, y, z) = (x, y, -z),
// which keeps the picture the same. Every twin is a GameObject named by its
// thingId ("kz.limit:mill-1") with a TwinState: the Unity panel sends it the
// twin's values from InfluxDB with SendMessage(thingId, "SetValues", json).

using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

public static class MineSceneBuilder
{
    const string ScenePath = "Assets/Scenes/Mine.unity";
    const string Generated = "Assets/Generated";
    const string BuildName = "MineUnderLimits";      // file names in build/: MineUnderLimits.loader.js, ...
    const string NS = "kz.limit:";

    static readonly string[] Twins = {
        "complex", "control", "planner", "pit", "face-1", "face-2", "face-3", "shovel-1", "shovel-2", "shovel-3",
        "crusher", "conveyor", "stockpile", "plant", "mill-1", "mill-2", "flotation", "thickener", "process-water",
        "water-intake", "tailings", "reclaim", "substation" };

    // positions on the 3D page (Three.js coordinates)
    static readonly Vector3 PIT = new Vector3(-92, 0, 22), CRUSHER = new Vector3(-22, 0, -22), PLANT = new Vector3(84, 0, -24),
        FLOT = new Vector3(124, 0, -44), THICK = new Vector3(148, 0, 14), TANK = new Vector3(100, 0, 30),
        TSF = new Vector3(50, 0, 128), INTAKE = new Vector3(204, 0, -30), SUB = new Vector3(-20, 0, -110),
        CONC = new Vector3(170, 0, -80), WORKSHOP = new Vector3(-118, 0, -88);
    const float PIT_R = 68, PIT_DEPTH = 44; const int BENCHES = 6;

    static readonly Dictionary<string, Transform> twin = new Dictionary<string, Transform>();
    static readonly Dictionary<int, Material> mats = new Dictionary<int, Material>();
    static Font font;
    static int meshCount;

    static Vector3 P(float x, float y, float z) => new Vector3(x, y, -z);
    static Vector3 P(Vector3 v) => new Vector3(v.x, v.y, -v.z);
    static Color C(int hex) => new Color(((hex >> 16) & 255) / 255f, ((hex >> 8) & 255) / 255f, (hex & 255) / 255f);
    static float BenchY(int k) => -PIT_DEPTH + PIT_DEPTH / BENCHES * k;
    static float BenchR(int k) => 16 + (PIT_R - 16) / BENCHES * k;

    // ---------------------------------------------------------------- entry points

    [MenuItem("Mine/Build scene")]
    public static void BuildSceneOnly() => BuildScene();

    [MenuItem("Mine/Build WebGL into build/")]
    public static void BuildWebGL()
    {
        BuildScene();
        PlayerSettings.companyName = "team-101";
        PlayerSettings.productName = "Рудник под лимитом";
        PlayerSettings.runInBackground = true;
        PlayerSettings.colorSpace = ColorSpace.Gamma;
        // The OpenEgiz Unity panel loads exactly four uncompressed files.
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.dataCaching = false;
        PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.None;
        PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.WebGL, ManagedStrippingLevel.Minimal);
        UseLegacyInput();
        EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.WebGL, BuildTarget.WebGL);

        var outDir = Path.Combine("Builds", BuildName);
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = outDir,
            target = BuildTarget.WebGL,
            options = BuildOptions.None,
        });
        if (report.summary.result != BuildResult.Succeeded)
        {
            Debug.LogError($"WebGL build failed: {report.summary.result}, {report.summary.totalErrors} errors");
            EditorApplication.Exit(1);
            return;
        }
        // team/unity -> repository root build/, served by the unity service on :8090
        var dest = Path.GetFullPath(Path.Combine(Directory.GetCurrentDirectory(), "..", "..", "build"));
        Directory.CreateDirectory(dest);
        foreach (var ext in new[] { "loader.js", "framework.js", "data", "wasm" })
        {
            var src = Path.Combine(outDir, "Build", $"{BuildName}.{ext}");
            File.Copy(src, Path.Combine(dest, $"{BuildName}.{ext}"), true);
            Debug.Log($"build/{BuildName}.{ext}: {new FileInfo(src).Length / 1024} KiB");
        }
    }

    // The scripts read the mouse with UnityEngine.Input; a new Unity 6 project may
    // default to the Input System package only, where those calls throw.
    static void UseLegacyInput()
    {
        var settings = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset");
        if (settings.Length == 0) return;
        var so = new SerializedObject(settings[0]);
        var handler = so.FindProperty("activeInputHandler");
        if (handler != null && handler.intValue == 1) { handler.intValue = 2; so.ApplyModifiedProperties(); }   // 1 = new only, 2 = both
    }

    // ---------------------------------------------------------------- the scene

    static void BuildScene()
    {
        twin.Clear(); mats.Clear(); meshCount = 0;
        if (AssetDatabase.IsValidFolder(Generated)) AssetDatabase.DeleteAsset(Generated);
        AssetDatabase.CreateFolder("Assets", "Generated");
        if (!AssetDatabase.IsValidFolder("Assets/Scenes")) AssetDatabase.CreateFolder("Assets", "Scenes");
        font = AssetDatabase.LoadAssetAtPath<Font>("Assets/Fonts/DejaVuSans.ttf");

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
        var root = new GameObject("Mine").transform;
        foreach (var n in Twins)
        {
            var go = new GameObject(NS + n);
            go.transform.SetParent(root, false);
            go.AddComponent<TwinState>();
            twin[n] = go.transform;
        }

        Environment(root);
        Terrain();
        Pit();
        CrushingAndStockpile();
        Plant();
        Water();
        Power();
        Site();

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        AssetDatabase.SaveAssets();
        Debug.Log($"Scene saved: {ScenePath}, {meshCount} generated meshes, {mats.Count} materials");
    }

    static void Environment(Transform root)
    {
        var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
        var cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = C(0x9cc3d8);
        cam.fieldOfView = 42; cam.nearClipPlane = 1; cam.farClipPlane = 4000;
        var orbit = camGo.AddComponent<OrbitCamera>();
        orbit.target = P(20, 0, 30); orbit.distance = 405; orbit.pitch = 41.8f; orbit.yaw = 5.7f;
        var picker = camGo.AddComponent<TwinPicker>();
        picker.font = font;

        var sunGo = new GameObject("Sun");
        var sun = sunGo.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.color = C(0xfff1dc); sun.intensity = 0.65f;           // SkyClock sets it from the model time
        sun.shadows = LightShadows.Hard;
        sunGo.transform.rotation = Quaternion.Euler(50, -30, 0);
        var sky = root.gameObject.AddComponent<SkyClock>();
        sky.sun = sun; sky.cam = cam;

        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = C(0xdfeeff) * 0.85f;
        RenderSettings.ambientEquatorColor = C(0xb7a67b) * 0.7f;
        RenderSettings.ambientGroundColor = C(0x6b5a3a) * 0.6f;
        RenderSettings.fog = true; RenderSettings.fogMode = FogMode.Linear;
        RenderSettings.fogStartDistance = 650; RenderSettings.fogEndDistance = 1300;
        RenderSettings.fogColor = cam.backgroundColor;
        RenderSettings.skybox = null;
        QualitySettings.shadowDistance = 900;
        QualitySettings.shadowResolution = ShadowResolution.Medium;
        QualitySettings.shadowCascades = 1;
    }

    // ---------------------------------------------------------------- terrain and pit

    static void Terrain()
    {
        // ground: a grid of 10 m cells without the pit; the pit's rim lip covers the jagged edge
        var v = new List<Vector3>(); var t = new List<int>();
        for (float x = -420; x < 420; x += 10)
            for (float z = -330; z < 330; z += 10)
            {
                if (new Vector2(x + 5 - PIT.x, z + 5 - PIT.z).magnitude < PIT_R + 8) continue;
                int i = v.Count;
                v.Add(P(x, 0, z)); v.Add(P(x + 10, 0, z)); v.Add(P(x + 10, 0, z + 10)); v.Add(P(x, 0, z + 10));
                t.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 });     // faces up once z is mirrored
            }
        var ground = MeshObject("Ground", v, t, Mat(0xb7a67b), null);
        ground.GetComponent<MeshRenderer>().shadowCastingMode = ShadowCastingMode.Off;
        Lathe("Pit rim", new[] { new Vector2(PIT_R, 0.02f), new Vector2(PIT_R + 17, 0.02f) }, P(PIT), Mat(0xb7a67b), twin["pit"]);
    }

    static void Pit()
    {
        // benches as lathe bands, coloured by depth: oxide cap to fresh sulphide rock
        var prof = new List<Vector2> { new Vector2(0, -PIT_DEPTH), new Vector2(BenchR(0), -PIT_DEPTH) };
        for (int k = 0; k < BENCHES; k++)
        {
            prof.Add(new Vector2(BenchR(k) + 3.5f, BenchY(k + 1)));
            prof.Add(new Vector2(BenchR(k + 1), BenchY(k + 1)));
        }
        Color top = C(0xa0603a), mid = C(0x8a7d6b), low = C(0x5c6863);
        for (int i = 0; i + 1 < prof.Count; i++)
        {
            float d = -(prof[i].y + prof[i + 1].y) / 2 / PIT_DEPTH;
            var c = d < 0.35f ? Color.Lerp(mid, top, 1 - d / 0.35f) : Color.Lerp(mid, low, (d - 0.35f) / 0.65f);
            Lathe($"Bench {i}", new[] { prof[i], prof[i + 1] }, P(PIT), Mat(c), twin["pit"]);
        }

        var faces = new[] {
            (n: "face-1", shovel: "shovel-1", angle: -Mathf.PI / 2 - 0.25f, bench: 4, color: 0xd59a4a, title: "Забой 1 · Северный"),
            (n: "face-2", shovel: "shovel-2", angle: 0.15f, bench: 3, color: 0xd8c08a, title: "Забой 2 · Восточный"),
            (n: "face-3", shovel: "shovel-3", angle: Mathf.PI / 2 + 0.2f, bench: 1, color: 0xc0583a, title: "Забой 3 · Южный, нижний") };
        var dumpTruck = Model("poly/dump-truck");
        var truckModel = Model("vehicles/garbage-truck");
        foreach (var f in faces)
        {
            float r = BenchR(f.bench) - 3, y = BenchY(f.bench), wallR = BenchR(f.bench) + 2;
            var pos = new Vector3(PIT.x + Mathf.Cos(f.angle) * r, y, PIT.z + Mathf.Sin(f.angle) * r);
            var wall = new Vector3(PIT.x + Mathf.Cos(f.angle) * wallR, y + 4, PIT.z + Mathf.Sin(f.angle) * wallR);
            var rock = Prim(PrimitiveType.Sphere, "Ore face", twin[f.n], P(wall), new Vector3(18, 10, 18), Mat(f.color, unique: true));
            var sc = rock.gameObject.AddComponent<StateColor>();
            sc.twin = f.n; sc.feature = "hard_ore"; sc.rule = StateColor.Rule.BoolTrue;
            sc.normal = C(f.color); sc.alert = C(0x6b4a7a); sc.renderers = new[] { rock };

            // rope shovel facing the wall
            var sh = new GameObject("Shovel").transform;
            sh.SetParent(twin[f.shovel], false);
            sh.position = P(pos);
            var look = P(PIT.x + Mathf.Cos(f.angle) * (wallR + 10), y, PIT.z + Mathf.Sin(f.angle) * (wallR + 10)) - sh.position;
            look.y = 0; sh.rotation = Quaternion.LookRotation(look);
            Prim(PrimitiveType.Cube, "Tracks", sh, Vector3.zero, new Vector3(7, 2, 8), Mat(0x22282b), local: true).transform.localPosition = new Vector3(0, 1, 0);
            var body = Prim(PrimitiveType.Cube, "Body", sh, new Vector3(0, 4.2f, -0.6f), new Vector3(6, 4.5f, 6.5f), Mat(0x3b4a52), local: true);
            var boom = Prim(PrimitiveType.Cube, "Boom", sh, new Vector3(0, 7.5f, 5.5f), new Vector3(1.1f, 1.1f, 11), Mat(0xc9a227), local: true);
            boom.transform.localRotation = Quaternion.Euler(-31.5f, 0, 0);
            Prim(PrimitiveType.Cube, "Dipper", sh, new Vector3(0, 4, 10), new Vector3(3, 2.6f, 2.6f), Mat(f.color), local: true);
            Highlight(f.shovel, body);
            Label(twin[f.n], P(pos.x, y + 16, pos.z), f.title,
                $"{{{f.shovel}.rate:N0}} т/ч · {{{f.n}.grade:N2}} % Cu · Wi {{{f.n}.bond_wi:N1}}");

            // haul road: spiral up the benches to the rim, then to the crusher
            float exit = Mathf.Atan2(CRUSHER.z - PIT.z, CRUSHER.x - PIT.x), a0 = f.angle, a1 = exit;
            while (a1 - a0 > Mathf.PI) a1 -= Mathf.PI * 2;
            while (a0 - a1 > Mathf.PI) a1 += Mathf.PI * 2;
            if (Mathf.Abs(a1 - a0) < 1.2f) a1 += a1 >= a0 ? Mathf.PI * 1.2f : -Mathf.PI * 1.2f;
            var road = new List<Vector3>();
            for (int i = 0; i <= 24; i++)
            {
                float s2 = i / 24f, yy = y * (1 - s2);
                float rr = BenchR(0) + (PIT_R - BenchR(0)) * (yy + PIT_DEPTH) / PIT_DEPTH - 4;
                float aa = a0 + (a1 - a0) * s2;
                road.Add(P(PIT.x + Mathf.Cos(aa) * rr, yy + 0.8f, PIT.z + Mathf.Sin(aa) * rr));
            }
            road.Add(P(CRUSHER.x - 8, 0.8f, CRUSHER.z + 4));
            var fleet = twin[f.shovel].gameObject.AddComponent<TruckFleet>();
            fleet.shovel = f.shovel;
            fleet.road = road.ToArray();
            var trucks = new List<Transform>(); var loads = new List<GameObject>();
            for (int i = 0; i < 4; i++)
            {
                var (truck, load) = dumpTruck != null ? DumpTruck(dumpTruck, twin[f.shovel]) : HaulTruck(truckModel, twin[f.shovel]);
                trucks.Add(truck); loads.Add(load);
            }
            fleet.trucks = trucks.ToArray(); fleet.loads = loads.ToArray();
        }

        // a dozer cleaning the bench of face 1 and a water truck on the haul road at the rim
        var dozer = Model("poly/bulldozer");
        if (dozer != null)
        {
            float a = -Mathf.PI / 2 + 0.25f, r = BenchR(4) - 4;
            Fit(dozer, twin["pit"], P(PIT.x + Mathf.Cos(a) * r, BenchY(4), PIT.z + Mathf.Sin(a) * r), 8, 2, a + Mathf.PI / 2);
        }
        var waterTruck = Model("poly/water-truck");
        if (waterTruck != null) Fit(waterTruck, twin["pit"], P(CRUSHER.x - 20, 0, CRUSHER.z + 16), 8.5f, 2, 0.6f, 90);
    }

    // The Poly Pizza dump truck faces -z: turned inside its holder so that the
    // holder's +z (TruckFleet's LookRotation) is forward. It is one mesh, so the
    // ore it carries is a heap on the body, shown only on the way up.
    static (Transform, GameObject) DumpTruck(GameObject model, Transform parent)
    {
        var g = Fit(model, parent, Vector3.zero, 8, 2, 0, 180);
        g.name = "Truck";
        var size = g.GetComponent<BoxCollider>().size;
        var load = Prim(PrimitiveType.Cube, "Load", g, new Vector3(0, size.y * 0.84f, -size.z * 0.17f),
            new Vector3(size.x * 0.7f, size.y * 0.2f, size.z * 0.42f), Mat(0x9b6a45), local: true);
        Object.DestroyImmediate(load.GetComponent<Collider>());
        return (g, load.gameObject);
    }

    static (Transform, GameObject) HaulTruck(GameObject model, Transform parent)
    {
        if (model == null)          // no Kenney model: a box truck, as on the 3D page before the models
        {
            var g = new GameObject("Truck").transform;
            g.SetParent(parent, false);
            Prim(PrimitiveType.Cube, "Body", g, new Vector3(0, 1.6f, 0), new Vector3(3.4f, 1.6f, 6), Mat(0xe0b400), local: true);
            Prim(PrimitiveType.Cube, "Cab", g, new Vector3(0, 2.4f, 2.9f), new Vector3(3.2f, 1.6f, 1.6f), Mat(0x3d4449), local: true);
            var load = Prim(PrimitiveType.Cube, "Load", g, new Vector3(0, 3, -0.6f), new Vector3(2.8f, 1.2f, 4.2f), Mat(0x9b6a45), local: true);
            return (g, load.gameObject);
        }
        var m = Place(model, parent, Vector3.zero, 2.2f, 0);
        Find(m, "arm")?.gameObject.SetActive(false);          // the garbage-truck arms; a haul truck has none
        return (m, Find(m, "trash")?.gameObject);
    }

    // ---------------------------------------------------------------- crushing and stockpile

    static void CrushingAndStockpile()
    {
        var crusher = Prim(PrimitiveType.Cube, "Crusher", twin["crusher"], P(CRUSHER.x, 8, CRUSHER.z), new Vector3(14, 16, 14), Mat(0x7d8b92, unique: true));
        var hopper = Model("factory/hopper-high-round");
        if (hopper != null) Recolor(Fit(hopper, twin["crusher"], P(CRUSHER.x - 9, 0, CRUSHER.z + 5), 11, 1, 0), 0x5d666b);
        else Prim(PrimitiveType.Cylinder, "Hopper", twin["crusher"], P(CRUSHER.x - 8, 3, CRUSHER.z + 4), new Vector3(10, 3, 10), Mat(0x5d666b));
        Highlight("crusher", crusher);
        Label(twin["crusher"], P(CRUSHER.x, 24, CRUSHER.z), "Дробилка ККД", "{crusher.throughput:N0} т/ч · {crusher.load:N0} %");

        var stock = new[] { new Vector3(10, 0, -58), new Vector3(28, 0, -62), new Vector3(46, 0, -58) };
        int[] colors = { 0xd59a4a, 0xd8c08a, 0xc0583a };
        var pileRenderers = new List<Renderer>();
        var cone = ConeMesh();
        for (int i = 0; i < 3; i++)
        {
            var go = new GameObject($"Pile {i + 1}");
            go.transform.SetParent(twin["stockpile"], false);
            go.transform.position = P(stock[i]);
            go.AddComponent<MeshFilter>().sharedMesh = cone;
            var mr = go.AddComponent<MeshRenderer>(); mr.sharedMaterial = Mat(colors[i], unique: true);
            go.AddComponent<MeshCollider>().sharedMesh = cone;
            pileRenderers.Add(mr);
            var sbf = go.AddComponent<ScaleByFeature>();
            sbf.twin = "stockpile"; sbf.feature = $"section_{i + 1}"; sbf.mode = ScaleByFeature.Mode.CubeRootUniform;
            sbf.factor = 1f / 11.6f; sbf.min = 0.6f; sbf.max = 20f;
        }
        Highlight("stockpile", pileRenderers.ToArray());
        Label(twin["stockpile"], P(6, 24, -72), "Склад руды (3 сорта)", "{stockpile.total:N0} т · {stockpile.fill:N0} %");
        Flow("crusher", "throughput", 3600, twin["conveyor"], new[] { P(CRUSHER.x + 7, 12, CRUSHER.z), P(2, 16, -42), P(28, 20, -60) },
            0x9b6a45, 1.6f, 40, 0.9f, 0x4a5257);
        Flow("plant", "feed", 3200, twin["conveyor"], new[] { P(28, 3, -52), P(48, 10, -38), P(PLANT.x - 18, 12, PLANT.z) },
            0x9b6a45, 1.5f, 36, 0.8f, 0x4a5257);

        var loader = Model("vehicles/tractor-shovel");
        if (loader != null) Place(loader, twin["stockpile"], P(-4, 0, -66), 3, Mathf.PI / 2 - 0.3f);
    }

    // ---------------------------------------------------------------- the plant

    static void Plant()
    {
        Prim(PrimitiveType.Cube, "Plant floor", twin["plant"], P(PLANT.x, 0.5f, PLANT.z), new Vector3(46, 1, 48), Mat(0x6f777b));
        // an open steel frame instead of a solid roof, so the grinding lines stay visible from above
        var steel = Mat(0x6a7479);
        foreach (var (dx, dz) in new[] { (-22, -23), (22, -23), (-22, 23), (22, 23), (-22, 0), (22, 0) })
            Prim(PrimitiveType.Cube, "Column", twin["plant"], P(PLANT.x + dx, 13, PLANT.z + dz), new Vector3(1.2f, 26, 1.2f), steel);
        foreach (var dz in new[] { -23, 0, 23 })
            Prim(PrimitiveType.Cube, "Roof girder", twin["plant"], P(PLANT.x, 26, PLANT.z + dz), new Vector3(46, 1, 1), steel);
        for (int k = -2; k <= 2; k++)
            Prim(PrimitiveType.Cube, "Roof beam", twin["plant"], P(PLANT.x + k * 11, 26.4f, PLANT.z), new Vector3(0.7f, 0.7f, 48), steel);
        Prim(PrimitiveType.Cube, "Crane rail", twin["plant"], P(PLANT.x, 22, PLANT.z - 23), new Vector3(46, 0.8f, 0.8f), Mat(0xc9a227));
        Prim(PrimitiveType.Cube, "Crane rail", twin["plant"], P(PLANT.x, 22, PLANT.z + 23), new Vector3(46, 0.8f, 0.8f), Mat(0xc9a227));
        Prim(PrimitiveType.Cube, "Overhead crane", twin["plant"], P(PLANT.x - 14, 22.8f, PLANT.z), new Vector3(2, 1.4f, 47), Mat(0xc9a227));

        for (int i = 0; i < 2; i++)
        {
            var name = $"mill-{i + 1}";
            float z = PLANT.z - 11 + i * 22;
            float outward = i == 0 ? -1 : 1;           // the drives stand on the outer side of each line
            var shells = new List<Renderer>();
            var sag = GrindingMill(twin[name], P(PLANT.x - 9, 10, z), 8f, 6f, 2.6f, 2.4f, outward, true, shells);
            var ball = GrindingMill(twin[name], P(PLANT.x + 12, 7, z), 5f, 11f, 1.9f, 1.6f, outward, false, shells);
            Hydrocyclones(twin[name], new Vector3(PLANT.x + 1.5f, 0, z - outward * 6));
            var md = twin[name].gameObject.AddComponent<MillDrum>();
            md.twin = name; md.drum = sag; md.drums = new[] { ball }; md.shells = shells.ToArray();
            Highlight(name, shells.ToArray());
        }
        Label(twin["mill-1"], P(PLANT.x - 14, 40, PLANT.z - 10), "Измельчение: 2 линии МПСИ + шаровая",
            "линия 1: {mill-1.feed:N0} т/ч · {mill-1.power:N1} МВт · {mill-1.state}\nлиния 2: {mill-2.feed:N0} т/ч · {mill-2.power:N1} МВт · {mill-2.state}");

        // flotation cells with froth
        var cells = new List<Renderer>();
        for (int i = 0; i < 8; i++)
        {
            float x = FLOT.x + (i % 4) * 8, z = FLOT.z + (i / 4) * 9;
            cells.Add(Prim(PrimitiveType.Cylinder, "Cell", twin["flotation"], P(x, 3, z), new Vector3(6.8f, 3, 6.8f), Mat(0x8796a0)));
            Prim(PrimitiveType.Cylinder, "Froth", twin["flotation"], P(x, 6.05f, z), new Vector3(6.4f, 0.05f, 6.4f), Mat(0xc8c26a));
        }
        Label(twin["flotation"], P(FLOT.x + 30, 4, FLOT.z + 18), "Флотация", "извлечение {flotation.recovery:N1} % · {flotation.copper:N2} т Cu/ч");
        Flow("plant", "feed", 3200, twin["flotation"], new[] { P(PLANT.x + 20, 4, PLANT.z), P(FLOT.x - 6, 4, FLOT.z + 4) }, 0x8f8a7a, 1, 14, 0.6f, 0x8a9399);

        // tailings thickener
        Prim(PrimitiveType.Cylinder, "Thickener", twin["thickener"], P(THICK.x, 2, THICK.z), new Vector3(30, 2, 30), Mat(0xa0a6a8));
        var water = Prim(PrimitiveType.Cylinder, "Thickener water", twin["thickener"], P(THICK.x, 4.05f, THICK.z), new Vector3(28.4f, 0.05f, 28.4f), Mat(0x6b7f7c, unique: true));
        var sc = water.gameObject.AddComponent<StateColor>();
        sc.twin = "thickener"; sc.feature = "mode"; sc.rule = StateColor.Rule.StringEquals; sc.equals = "high-density";
        sc.normal = C(0x6b7f7c); sc.alert = C(0x9a8f72); sc.renderers = new[] { water };
        Label(twin["thickener"], P(THICK.x, 14, THICK.z + 4), "Сгуститель хвостов", "{thickener.underflow_solids:N1} % твёрдого · {thickener.mode}");
        Flow("plant", "feed", 3200, twin["thickener"], new[] { P(FLOT.x + 26, 4, FLOT.z + 10), P(THICK.x, 6, THICK.z - 14) }, 0x8f8a7a, 1, 14, 0.6f, 0x8a9399);

        // copper concentrate: flow to the shed
        Flow("flotation", "concentrate", 50, twin["flotation"], new[] { P(FLOT.x + 28, 4, FLOT.z - 2), P(150, 6, -62), P(CONC.x - 14, 5, CONC.z + 6) },
            0x5f6b55, 1.4f, 18, 0.7f, 0x4a5257);
        Label(twin["flotation"], P(CONC.x + 4, 26, CONC.z - 4), "Склад медного концентрата", "{flotation.concentrate:N1} т/ч");
    }


    // One tumbling mill along x: shell with flanges and liner bolt rows, conical
    // heads, trunnions on bearing pedestals, girth gear with pinion, gearbox and
    // motor on the `outward` side; a SAG mill also gets a feed chute and the
    // discharge trommel. Returns the pivot that turns (shell, heads, gear,
    // trunnions, trommel); shell and heads go to `shells` for the state colour.
    static Transform GrindingMill(Transform parent, Vector3 axis, float r, float len, float headLen, float trunnion,
        float outward, bool sag, List<Renderer> shells)
    {
        var pivot = new GameObject(sag ? "SAG mill" : "Ball mill").transform;
        pivot.SetParent(parent, false);
        pivot.position = axis;
        var shell = Mat(0x4f8fa8, unique: true);
        var dark = Mat(0x2c3e47);
        Renderer AlongX(PrimitiveType t, string n, float x, float radius, float length, Material m)
        {
            var rr = Prim(t, n, pivot, new Vector3(x, 0, 0), new Vector3(radius * 2, length / 2, radius * 2), m, local: true);
            rr.transform.localRotation = Quaternion.Euler(0, 0, 90);
            return rr;
        }
        shells.Add(AlongX(PrimitiveType.Cylinder, "Shell", 0, r, len, shell));
        foreach (var sx in new[] { -1f, 1f })
        {
            AlongX(PrimitiveType.Cylinder, "Flange", sx * (len / 2 - 0.2f), r + 0.35f, 0.5f, dark);
            var head = Frustum("Head", pivot, r, trunnion + 0.3f, headLen, shell);
            head.transform.localPosition = new Vector3(sx * (len / 2 + headLen / 2), 0, 0);
            head.transform.localRotation = Quaternion.Euler(0, 0, sx > 0 ? -90 : 90);
            shells.Add(head);
            AlongX(PrimitiveType.Cylinder, "Trunnion", sx * (len / 2 + headLen + 1), trunnion, 2, Mat(0x7f8d94));
        }
        for (int k = 0; k < 12; k++)                      // rows of liner bolts: they show the drum turning
        {
            float a = k / 12f * 360f;
            var bar = Prim(PrimitiveType.Cube, "Liner bolts", pivot, Quaternion.Euler(a, 0, 0) * new Vector3(0, r + 0.08f, 0),
                new Vector3(len - 1, 0.25f, 0.5f), dark, local: true);
            bar.transform.localRotation = Quaternion.Euler(a, 0, 0);
            Object.DestroyImmediate(bar.GetComponent<Collider>());
        }
        float gearX = (sag ? 1 : -1) * (len / 2 - 1.2f);
        AlongX(PrimitiveType.Cylinder, "Girth gear", gearX, r + 1.1f, 0.9f, Mat(0x3a3f42));
        if (sag)
        {
            var trommel = AlongX(PrimitiveType.Cylinder, "Trommel screen", len / 2 + headLen + 3.5f, trunnion - 0.2f, 3.5f, Mat(0x8a8f86));
            Object.DestroyImmediate(trommel.GetComponent<Collider>());
        }

        // static parts, in the parent's frame
        var pedestal = Mat(0x6a7479);
        float pedH = axis.y - trunnion;
        foreach (var sx in new[] { -1f, 1f })
        {
            float x = axis.x + sx * (len / 2 + headLen + 1);
            Prim(PrimitiveType.Cube, "Bearing pedestal", parent, new Vector3(x, pedH / 2 + 0.5f, axis.z), new Vector3(3, pedH, trunnion * 2 + 2), pedestal);
            Prim(PrimitiveType.Cube, "Bearing cap", parent, new Vector3(x, axis.y + trunnion * 0.6f, axis.z), new Vector3(2.4f, 1, trunnion * 2 + 1.4f), pedestal);
        }
        float total = len + headLen * 2 + 4;
        Prim(PrimitiveType.Cube, "Foundation", parent, new Vector3(axis.x, 0.75f, axis.z), new Vector3(total + 2, 0.5f, r * 2 + 3), Mat(0x8d8a82));
        // drive: pinion under the gear, gearbox, motor, on the outer side
        float dz = -outward * (r + 3.2f);                  // P() mirrors z: outward in Three.js is -z in Unity
        float gx = axis.x + gearX;
        Prim(PrimitiveType.Cube, "Pinion housing", parent, new Vector3(gx, axis.y - r * 0.55f, axis.z + dz * 0.75f), new Vector3(1.8f, 2.4f, 2.6f), Mat(0x3a3f42));
        Prim(PrimitiveType.Cube, "Gearbox", parent, new Vector3(gx - 3.5f, 2.6f, axis.z + dz), new Vector3(3.6f, 3.2f, 3.4f), Mat(0x5c6b73));
        var motor = Prim(PrimitiveType.Cylinder, "Motor", parent, new Vector3(gx - 8f, 2.8f, axis.z + dz), new Vector3(3.6f, 2.6f, 3.6f), Mat(0x37586b));
        motor.transform.rotation = Quaternion.Euler(0, 0, 90);
        Prim(PrimitiveType.Cube, "Drive shaft", parent, new Vector3(gx - 1.8f, 2.6f, axis.z + dz * 0.88f), new Vector3(3.4f, 0.6f, 0.6f), Mat(0x7f8d94));
        if (sag)
        {
            // feed chute from the conveyor into the feed trunnion
            float fx = axis.x - (len / 2 + headLen + 2.2f);
            var chute = Prim(PrimitiveType.Cube, "Feed chute", parent, new Vector3(fx - 1.5f, axis.y + 3.2f, axis.z), new Vector3(2.4f, 7, 3), Mat(0x5d666b));
            chute.transform.rotation = Quaternion.Euler(0, 0, -28);
        }
        return pivot;
    }

    // hydrocyclone cluster on a stand between the SAG and the ball mill, beside the line, with its feed pump
    static void Hydrocyclones(Transform parent, Vector3 at)
    {
        var steel = Mat(0x6a7479);
        var c = P(at);
        foreach (var (dx, dz) in new[] { (-2.2f, -2.2f), (2.2f, -2.2f), (-2.2f, 2.2f), (2.2f, 2.2f) })
            Prim(PrimitiveType.Cube, "Stand leg", parent, c + new Vector3(dx, 6, dz), new Vector3(0.4f, 12, 0.4f), steel);
        Prim(PrimitiveType.Cube, "Platform", parent, c + new Vector3(0, 12, 0), new Vector3(6, 0.4f, 6), steel);
        Prim(PrimitiveType.Cylinder, "Distributor", parent, c + new Vector3(0, 14, 0), new Vector3(2.2f, 1, 2.2f), Mat(0x7f8d94));
        for (int k = 0; k < 6; k++)
        {
            float a = k / 6f * Mathf.PI * 2;
            var pos = c + new Vector3(Mathf.Cos(a) * 2.1f, 13.6f, Mathf.Sin(a) * 2.1f);
            var cone = Frustum("Hydrocyclone", parent, 0.15f, 0.55f, 3.2f, Mat(0xd6dade));
            cone.transform.position = pos;
            cone.transform.rotation = Quaternion.Euler(Mathf.Sin(a) * 12, 0, -Mathf.Cos(a) * 12);
        }
        Prim(PrimitiveType.Cube, "Cyclone feed pump", parent, c + new Vector3(-3.6f, 1.6f, 0), new Vector3(2, 2.2f, 2.6f), Mat(0x37586b));
    }

    // a closed frustum along local y, centred: radius r0 at the bottom (y = -h/2), r1 at the top
    static Renderer Frustum(string name, Transform parent, float r0, float r1, float h, Material mat)
    {
        const int seg = 32;
        var v = new List<Vector3>(); var t = new List<int>();
        for (int s = 0; s < seg; s++)
        {
            float a0 = s * Mathf.PI * 2 / seg, a1 = (s + 1) * Mathf.PI * 2 / seg;
            int i = v.Count;
            v.Add(new Vector3(Mathf.Cos(a0) * r0, -h / 2, Mathf.Sin(a0) * r0)); v.Add(new Vector3(Mathf.Cos(a1) * r0, -h / 2, Mathf.Sin(a1) * r0));
            v.Add(new Vector3(Mathf.Cos(a1) * r1, h / 2, Mathf.Sin(a1) * r1)); v.Add(new Vector3(Mathf.Cos(a0) * r1, h / 2, Mathf.Sin(a0) * r1));
            t.AddRange(new[] { i, i + 2, i + 1, i, i + 3, i + 2 });
            int j = v.Count;                                   // the end caps
            v.Add(new Vector3(0, h / 2, 0)); v.Add(new Vector3(Mathf.Cos(a0) * r1, h / 2, Mathf.Sin(a0) * r1)); v.Add(new Vector3(Mathf.Cos(a1) * r1, h / 2, Mathf.Sin(a1) * r1));
            v.Add(new Vector3(0, -h / 2, 0)); v.Add(new Vector3(Mathf.Cos(a1) * r0, -h / 2, Mathf.Sin(a1) * r0)); v.Add(new Vector3(Mathf.Cos(a0) * r0, -h / 2, Mathf.Sin(a0) * r0));
            t.AddRange(new[] { j, j + 2, j + 1, j + 3, j + 5, j + 4 });
        }
        var go = MeshObject(name, v, t, mat, parent);
        return go.GetComponent<MeshRenderer>();
    }

    // ---------------------------------------------------------------- water

    static void Water()
    {
        // process water tank: a glass shell and the water level inside
        var shell = Prim(PrimitiveType.Cylinder, "Tank", twin["process-water"], P(TANK.x, 8, TANK.z), new Vector3(16, 8, 16), Mat(0xc7d3d9, alpha: 0.3f));
        shell.shadowCastingMode = ShadowCastingMode.Off;
        var level = new GameObject("Water level").transform;
        level.SetParent(twin["process-water"], false);
        level.position = P(TANK.x, 0, TANK.z);
        var w = Prim(PrimitiveType.Cylinder, "Water", level, Vector3.zero, new Vector3(15.2f, 0.5f, 15.2f), Mat(0x3c9fd6, unique: true), local: true);
        var sbf = level.gameObject.AddComponent<ScaleByFeature>();
        sbf.twin = "process-water"; sbf.feature = "level"; sbf.mode = ScaleByFeature.Mode.HeightFromBase; sbf.factor = 0.155f; sbf.min = 0.2f; sbf.max = 15.5f;
        var sc = w.gameObject.AddComponent<StateColor>();
        sc.twin = "process-water"; sc.feature = "level"; sc.rule = StateColor.Rule.BelowValue; sc.threshold = 20;
        sc.normal = C(0x3c9fd6); sc.alert = C(0xd0574f); sc.renderers = new[] { w };
        Label(twin["process-water"], P(TANK.x - 6, 22, TANK.z + 6), "Резервуар оборотной воды", "{process-water.level:N0} % · расход {process-water.demand:N0} м³/ч");
        Flow("process-water", "demand", 2800, twin["process-water"], new[] { P(TANK.x - 8, 3, TANK.z), P(PLANT.x + 8, 4, PLANT.z + 24) }, 0x4fb3e8, 1, 18, 0.7f, 0x5d7f91);

        // tailings storage: dam, beach, pond sized by area
        Lathe("Dam", new[] { new Vector2(54, 0), new Vector2(57, 6), new Vector2(62, 6), new Vector2(70, 0) }, P(TSF), Mat(0x9d8e70), twin["tailings"]);
        Prim(PrimitiveType.Cylinder, "Beach", twin["tailings"], P(TSF.x, 0.3f, TSF.z), new Vector3(112, 0.3f, 112), Mat(0xcfc3a2));
        var pondT = new GameObject("Pond").transform;
        pondT.SetParent(twin["tailings"], false);
        pondT.position = P(TSF.x + 5, 0.7f, TSF.z + 6);
        var pond = Prim(PrimitiveType.Cylinder, "Water", pondT, Vector3.zero, new Vector3(1, 0.05f, 1), Mat(0x3f8fb8, unique: true), local: true);
        pond.shadowCastingMode = ShadowCastingMode.Off;
        var ps = pondT.gameObject.AddComponent<ScaleByFeature>();
        ps.twin = "tailings"; ps.feature = "pond_area"; ps.mode = ScaleByFeature.Mode.SqrtFlat; ps.factor = 63.25f; ps.min = 10; ps.max = 108;
        pondT.localScale = new Vector3(80, 1, 80);
        Highlight("tailings", pond);
        Label(twin["tailings"], P(TSF.x + 20, 16, TSF.z + 22), "Хвостохранилище", "пруд {tailings.pond_volume:N0} м³");
        Flow("thickener", "water_to_tailings", 2800, twin["tailings"], new[] { P(THICK.x - 6, 3, THICK.z + 14), P(118, 2, 70), P(TSF.x + 40, 3, TSF.z - 38) },
            0x9a9384, 1.2f, 30, 0.9f, 0x6d6a62);

        var barge = Prim(PrimitiveType.Cube, "Barge", twin["reclaim"], P(TSF.x - 6, 2.5f, TSF.z - 26), new Vector3(8, 3, 5), Mat(0xe07a3f, unique: true));
        Highlight("reclaim", barge);
        Label(twin["reclaim"], P(TSF.x - 30, 12, TSF.z - 22), "Насосная оборотной воды", "{reclaim.flow:N0} / {reclaim.capacity:N0} м³/ч");
        Flow("reclaim", "flow", 1100, twin["reclaim"], new[] { P(TSF.x - 6, 3, TSF.z - 26), P(TSF.x + 4, 8, TSF.z - 64), P(TANK.x - 4, 3, TANK.z + 8) },
            0x4fb3e8, 1.3f, 30, 0.9f, 0x5d7f91);

        // canal and intake
        var canal = Prim(PrimitiveType.Cube, "Canal", twin["water-intake"], P(222, 0.15f, 0), new Vector3(22, 0.3f, 660), Mat(0x2f7fae));
        canal.shadowCastingMode = ShadowCastingMode.Off;
        var intake = Prim(PrimitiveType.Cube, "Intake", twin["water-intake"], P(INTAKE.x, 4.5f, INTAKE.z), new Vector3(14, 9, 12), Mat(0x8a969c, unique: true));
        var pipe = Flow("water-intake", "flow", 1750, twin["water-intake"],
            new[] { P(INTAKE.x - 8, 2, INTAKE.z), P(180, 2, -10), P(150, 2, 40), P(TANK.x + 8, 3, TANK.z) }, 0x6fd0ff, 1.4f, 40, 1.0f, 0x5d7f91);
        var pc = pipe.AddComponent<StateColor>();
        pc.twin = "water-intake"; pc.feature = "flow"; pc.rule = StateColor.Rule.RatioAbove; pc.limitFeature = "limit"; pc.threshold = 0.97f;
        pc.normal = C(0x5d7f91); pc.alert = C(0xe0883a); pc.renderers = new[] { pipe.GetComponent<Renderer>() };
        Highlight("water-intake", intake);
        Label(twin["water-intake"], P(INTAKE.x - 30, 18, INTAKE.z - 4), "Водозабор с канала", "{water-intake.flow:N0} / {water-intake.limit:N0} м³/ч");
    }

    // ---------------------------------------------------------------- power

    static void Power()
    {
        var sub = twin["substation"];
        Prim(PrimitiveType.Cube, "Pad", sub, P(SUB.x, 0.5f, SUB.z), new Vector3(40, 1, 26), Mat(0x6c7377));
        var trafos = new List<Renderer>();
        for (int i = 0; i < 3; i++)
        {
            trafos.Add(Prim(PrimitiveType.Cube, "Transformer", sub, P(SUB.x - 12 + i * 12, 4.5f, SUB.z + 4), new Vector3(6, 7, 5), Mat(0x8e9aa1, unique: true)));
            Prim(PrimitiveType.Cube, "Gantry post", sub, P(SUB.x - 12 + i * 12, 7, SUB.z - 8), new Vector3(0.8f, 14, 0.8f), Mat(0x5b6266));
        }
        Prim(PrimitiveType.Cube, "Gantry", sub, P(SUB.x, 14, SUB.z - 8), new Vector3(30, 0.8f, 0.8f), Mat(0x5b6266));
        var subColor = sub.gameObject.AddComponent<StateColor>();
        subColor.twin = "substation"; subColor.feature = "load"; subColor.rule = StateColor.Rule.RatioAbove; subColor.limitFeature = "limit"; subColor.threshold = 0.97f;
        subColor.normal = C(0x8e9aa1); subColor.alert = C(0xd9573f); subColor.renderers = trafos.ToArray();
        Highlight("substation", trafos.ToArray());
        Label(sub, P(SUB.x, 22, SUB.z), "Подстанция 220/10 кВ", "{substation.load:N1} / {substation.limit:N0} МВт");

        PowerLine("Line to pit", new Vector2(-60, -40), "crusher", "throughput", 3600);
        PowerLine("Line to plant", new Vector2(PLANT.x - 10, PLANT.z - 23), "plant", "power", 60);
        PowerLine("Line to intake", new Vector2(INTAKE.x, INTAKE.z - 6), "water-intake", "power", 2500);
        PowerLine("Line to reclaim", new Vector2(TSF.x - 64, TSF.z - 40), "reclaim", "power", 900);
    }

    static void PowerLine(string name, Vector2 to, string rateTwin, string rateFeature, float max)
    {
        var from = new Vector3(SUB.x, 14, SUB.z - 8);
        var end = new Vector3(to.x, 14, to.y);
        int towers = Mathf.Max(2, Mathf.RoundToInt(Vector3.Distance(from, end) / 45));
        var pts = new List<Vector3>();
        var towerModel = Model("poly/transmission-tower");
        var along = P(end) - P(from); along.y = 0;
        for (int i = 0; i <= towers; i++)
        {
            var p = Vector3.Lerp(from, end, (float)i / towers);
            if (towerModel != null)
            {
                // the lattice tower's crossarm is along its x: turn its z along the line
                var tw = Fit(towerModel, twin["substation"], P(p.x, 0, p.z), 17, 1, 0);
                tw.rotation = Quaternion.LookRotation(along);
                Recolor(tw, 0x6b7378);
            }
            else
            {
                Prim(PrimitiveType.Cube, "Tower", twin["substation"], P(p.x, 7, p.z), new Vector3(0.8f, 16, 0.8f), Mat(0x5b6266));
                Prim(PrimitiveType.Cube, "Crossarm", twin["substation"], P(p.x, 14.5f, p.z), new Vector3(5, 0.5f, 0.5f), Mat(0x5b6266));
            }
            pts.Add(P(p.x, 14.6f, p.z));
            if (i < towers) { var q = Vector3.Lerp(from, end, (i + 0.5f) / towers); pts.Add(P(q.x, 11.8f, q.z)); }
        }
        var line = Flow(rateTwin, rateFeature, max, twin["substation"], pts.ToArray(), 0xf2d14b, 1.4f, 20, 0.18f, 0x2a2f32);
        line.name = name;
        var markers = line.GetComponent<FlowMarkers>().markers;
        var sc = line.AddComponent<StateColor>();
        sc.twin = "substation"; sc.feature = "load"; sc.rule = StateColor.Rule.RatioAbove; sc.limitFeature = "limit"; sc.threshold = 0.97f;
        sc.normal = C(0xf2d14b); sc.alert = C(0xff6b4a);
        var rs = new List<Renderer>();
        foreach (var m in markers) rs.Add(m.GetComponent<Renderer>());
        sc.renderers = rs.ToArray();
    }

    // ---------------------------------------------------------------- site buildings (Kenney CC0)

    static void Site()
    {
        var site = new GameObject("Site").transform;
        var hangar = Model("industrial/building-j");
        if (hangar == null) { Debug.LogWarning("Kenney models not imported: the site buildings are left out"); return; }
        Place(hangar, site, P(WORKSHOP), 24, Mathf.PI);
        var dozer = Model("poly/bulldozer");
        if (dozer != null) Fit(dozer, twin["tailings"], P(TSF.x + 59, 6, TSF.z + 4), 8, 2, 0.4f);
        else Place(Model("vehicles/tractor-shovel"), twin["tailings"], P(TSF.x + 59, 6, TSF.z + 4), 3, 0.4f);
        var silos = Model("poly/silos");
        if (silos != null) Fit(silos, twin["flotation"], P(FLOT.x + 52, 0, FLOT.z - 4), 15, 1, Mathf.PI / 2);
        Place(Model("industrial/building-r"), twin["flotation"], P(CONC), 15, -Mathf.PI / 2);
        var container = Model("industrial/shipping-container-a");
        for (int i = 0; i < 6; i++) Place(container, site, P(CONC.x + 22 + (i % 3) * 5, 0, CONC.z - 10 + (i / 3) * 10), 9, 0);
        var tank = Model("industrial/detail-tank-large");
        Place(tank, twin["flotation"], P(FLOT.x + 6, 0, FLOT.z - 22), 9, 0);
        Place(tank, twin["flotation"], P(FLOT.x + 22, 0, FLOT.z - 22), 9, 0);
        Place(Model("industrial/building-e"), site, P(46, 0, -108), 17, Mathf.PI);
        Place(Model("industrial/building-c"), site, P(86, 0, -106), 15, Mathf.PI);
        Place(Model("industrial/water-tower"), site, P(116, 0, -102), 14, 0);
    }

    static GameObject Model(string path) => AssetDatabase.LoadAssetAtPath<GameObject>($"Assets/Models/{path}.glb");

    // rotY is the Three.js rotation about y; mirroring z turns it the other way
    static Transform Place(GameObject model, Transform parent, Vector3 pos, float scale, float rotY)
    {
        var go = (GameObject)PrefabUtility.InstantiatePrefab(model, parent);
        go.transform.position = pos;
        go.transform.localScale = Vector3.one * scale;
        go.transform.rotation = Quaternion.Euler(0, -rotY * Mathf.Rad2Deg, 0);
        // one box collider over the model, so a click picks its twin
        var bounds = new Bounds(pos, Vector3.zero);
        foreach (var r in go.GetComponentsInChildren<Renderer>()) { bounds.Encapsulate(r.bounds); r.shadowCastingMode = ShadowCastingMode.Off; }
        var box = go.AddComponent<BoxCollider>();
        box.center = go.transform.InverseTransformPoint(bounds.center);
        var size = go.transform.InverseTransformVector(bounds.size);
        box.size = new Vector3(Mathf.Abs(size.x), Mathf.Abs(size.y), Mathf.Abs(size.z));
        return go.transform;
    }

    // A model sized by its own bounds: `size` along `axis` (0 x, 1 y, 2 z of the
    // holder), standing on the ground at `pos`, centred, turned `turn` degrees
    // inside its holder (for models built facing another way) and the holder
    // turned by rotY like Place. Models from different sources come in any unit,
    // so this keeps the layout in the scene's units. The holder carries the
    // click collider; shadows are off, as for the Kenney models.
    static Transform Fit(GameObject model, Transform parent, Vector3 pos, float size, int axis, float rotY, float turn = 0)
    {
        var holder = new GameObject(model.name).transform;
        holder.SetParent(parent, false);
        holder.position = Vector3.zero; holder.rotation = Quaternion.identity;
        var go = (GameObject)PrefabUtility.InstantiatePrefab(model, holder);
        go.transform.localPosition = Vector3.zero;
        go.transform.localRotation = Quaternion.Euler(0, turn, 0);
        go.transform.localScale = Vector3.one;
        var rs = go.GetComponentsInChildren<Renderer>();
        var b = rs.Length > 0 ? rs[0].bounds : new Bounds();
        foreach (var r in rs) { b.Encapsulate(r.bounds); r.shadowCastingMode = ShadowCastingMode.Off; }
        float k = size / Mathf.Max(b.size[axis], 1e-4f);
        go.transform.localScale = Vector3.one * k;
        go.transform.localPosition = new Vector3(-b.center.x * k, -b.min.y * k, -b.center.z * k);
        var box = holder.gameObject.AddComponent<BoxCollider>();
        box.center = new Vector3(0, b.size.y * k / 2, 0);
        box.size = b.size * k;
        holder.position = pos;
        holder.rotation = Quaternion.Euler(0, -rotY * Mathf.Rad2Deg, 0);
        return holder;
    }

    // one flat colour over a model (the Kenney factory parts are lavender)
    static void Recolor(Transform t, int hex)
    {
        var m = Mat(hex);
        foreach (var r in t.GetComponentsInChildren<Renderer>())
        {
            var shared = new Material[r.sharedMaterials.Length];
            for (int i = 0; i < shared.Length; i++) shared[i] = m;
            r.sharedMaterials = shared;
        }
    }

    static Transform Find(Transform t, string name)
    {
        if (t.name == name) return t;
        foreach (Transform c in t) { var f = Find(c, name); if (f != null) return f; }
        return null;
    }

    // ---------------------------------------------------------------- helpers

    static Renderer Prim(PrimitiveType type, string name, Transform parent, Vector3 pos, Vector3 scale, Material mat, bool local = false)
    {
        var go = GameObject.CreatePrimitive(type);
        go.name = name;
        go.transform.SetParent(parent, false);
        if (local) go.transform.localPosition = pos; else go.transform.position = pos;
        go.transform.localScale = scale;
        var r = go.GetComponent<Renderer>();
        r.sharedMaterial = mat;
        return r;
    }

    static Material Mat(int hex, bool unique = false, float alpha = 1f) => Mat(C(hex), unique, alpha);

    static Material Mat(Color color, bool unique = false, float alpha = 1f)
    {
        int key = color.GetHashCode() ^ alpha.GetHashCode();
        if (!unique && mats.TryGetValue(key, out var m)) return m;
        m = new Material(Shader.Find("Standard")) { color = new Color(color.r, color.g, color.b, alpha) };
        m.SetFloat("_Glossiness", 0.15f);
        m.EnableKeyword("_EMISSION");             // the bottleneck pulse needs this variant in the build
        m.SetColor("_EmissionColor", Color.black);
        if (alpha < 1f)
        {
            m.SetFloat("_Mode", 3); m.SetInt("_SrcBlend", (int)BlendMode.SrcAlpha); m.SetInt("_DstBlend", (int)BlendMode.OneMinusSrcAlpha);
            m.SetInt("_ZWrite", 0); m.EnableKeyword("_ALPHABLEND_ON"); m.renderQueue = 3000;
        }
        AssetDatabase.CreateAsset(m, $"{Generated}/mat-{mats.Count}{(unique ? "-u" + meshCount++ : "")}.mat");
        if (!unique) mats[key] = m;
        return m;
    }

    static GameObject Flow(string twinName, string feature, float max, Transform parent, Vector3[] path,
        int color, float size, int count, float tube, int tubeColor)
    {
        var go = new GameObject($"Flow {twinName}.{feature}");
        go.transform.SetParent(parent, false);
        if (tube > 0)
        {
            var lr = go.AddComponent<LineRenderer>();
            lr.positionCount = path.Length; lr.SetPositions(path);
            lr.widthMultiplier = tube * 2; lr.numCornerVertices = 2;
            lr.sharedMaterial = Mat(tubeColor, unique: true);
            lr.shadowCastingMode = ShadowCastingMode.Off;
        }
        var markers = new Transform[count];
        var mm = Mat(color);
        for (int i = 0; i < count; i++)
        {
            var m = Prim(PrimitiveType.Cube, "Marker", go.transform, path[0], new Vector3(size, size * 0.7f, size), mm);
            Object.DestroyImmediate(m.GetComponent<Collider>());
            m.shadowCastingMode = ShadowCastingMode.Off;
            markers[i] = m.transform;
        }
        var fm = go.AddComponent<FlowMarkers>();
        fm.twin = twinName; fm.feature = feature; fm.max = max; fm.path = path; fm.markers = markers;
        return go;
    }

    static void Highlight(string twinName, params Renderer[] renderers)
    {
        var b = twin[twinName].gameObject.AddComponent<Bottleneck>();
        b.twin = twinName; b.renderers = renderers;
    }

    static void Label(Transform parent, Vector3 pos, string title, string template)
    {
        var go = new GameObject("Label " + title);
        go.transform.SetParent(parent, false);
        go.transform.position = pos;
        TextMesh Text(string n, Color c, Vector3 offset)
        {
            var t = new GameObject(n).AddComponent<TextMesh>();
            t.transform.SetParent(go.transform, false);
            t.transform.localPosition = offset;
            t.font = font; t.fontSize = 48; t.characterSize = 1f;          // about 5 m a line at the default camera distance
            t.anchor = TextAnchor.LowerCenter; t.alignment = TextAlignment.Center; t.color = c;
            t.GetComponent<MeshRenderer>().sharedMaterial = font.material;
            return t;
        }
        var shadow = Text("Shadow", new Color(0, 0, 0, 0.85f), new Vector3(0.4f, -0.4f, 0.3f));
        var text = Text("Text", Color.white, Vector3.zero);
        var label = go.AddComponent<TwinLabel>();
        label.title = title; label.template = template; label.text = text; label.shadow = shadow;
        text.text = shadow.text = title;
    }

    static GameObject MeshObject(string name, List<Vector3> v, List<int> t, Material mat, Transform parent)
    {
        var mesh = new Mesh { name = name, indexFormat = v.Count > 65000 ? IndexFormat.UInt32 : IndexFormat.UInt16 };
        mesh.SetVertices(v); mesh.SetTriangles(t, 0);
        mesh.RecalculateNormals(); mesh.RecalculateBounds();
        AssetDatabase.CreateAsset(mesh, $"{Generated}/mesh-{meshCount++}.asset");
        var go = new GameObject(name);
        if (parent != null) go.transform.SetParent(parent, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
        go.AddComponent<MeshCollider>().sharedMesh = mesh;
        return go;
    }

    // a surface of revolution of a profile (radius, height) around the y axis, flat shaded
    static void Lathe(string name, Vector2[] profile, Vector3 center, Material mat, Transform parent)
    {
        const int seg = 72;
        var v = new List<Vector3>(); var t = new List<int>();
        for (int p = 0; p + 1 < profile.Length; p++)
            for (int s = 0; s < seg; s++)
            {
                float a0 = s * Mathf.PI * 2 / seg, a1 = (s + 1) * Mathf.PI * 2 / seg;
                Vector3 V(Vector2 q, float a) => center + new Vector3(Mathf.Cos(a) * q.x, q.y, Mathf.Sin(a) * q.x);
                // both sides, each with its own vertices so that the normals do not cancel out:
                // the benches are seen from above and from across the pit
                for (int side = 0; side < 2; side++)
                {
                    int i = v.Count;
                    v.Add(V(profile[p], a0)); v.Add(V(profile[p], a1)); v.Add(V(profile[p + 1], a1)); v.Add(V(profile[p + 1], a0));
                    t.AddRange(side == 0 ? new[] { i, i + 2, i + 1, i, i + 3, i + 2 } : new[] { i, i + 1, i + 2, i, i + 2, i + 3 });
                }
            }
        MeshObject(name, v, t, mat, parent);
    }

    // a cone of radius 1.33 and height 1, centred on its middle, like the stockpile cones of the 3D page
    static Mesh ConeMesh()
    {
        const int seg = 32;
        var v = new List<Vector3>(); var t = new List<int>();
        for (int s = 0; s < seg; s++)
        {
            float a0 = s * Mathf.PI * 2 / seg, a1 = (s + 1) * Mathf.PI * 2 / seg;
            int i = v.Count;
            v.Add(new Vector3(0, 0.5f, 0));
            v.Add(new Vector3(Mathf.Cos(a1) * 1.33f, -0.5f, Mathf.Sin(a1) * 1.33f));
            v.Add(new Vector3(Mathf.Cos(a0) * 1.33f, -0.5f, Mathf.Sin(a0) * 1.33f));
            t.AddRange(new[] { i, i + 1, i + 2 });
        }
        var mesh = new Mesh { name = "Cone" };
        mesh.SetVertices(v); mesh.SetTriangles(t, 0);
        mesh.RecalculateNormals(); mesh.RecalculateBounds();
        AssetDatabase.CreateAsset(mesh, $"{Generated}/mesh-{meshCount++}.asset");
        return mesh;
    }
}
