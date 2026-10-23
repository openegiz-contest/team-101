// Click an object to see its twin: a card with every value Grafana sent for
// it, and the event "SelectTwin" with the twin's thingId, which the Unity
// panel stores in the dashboard variable `twin` (a table next to the scene
// then lists that twin). Before the first data a banner says what to wait for.

using System.Linq;
using System.Runtime.InteropServices;
using UnityEngine;

public class TwinPicker : MonoBehaviour
{
#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void SelectTwin(string id);
#else
    static void SelectTwin(string id) { }
#endif

    public Font font;
    TwinState picked;
    Vector3 down;
    GUIStyle box, head;

    void Update()
    {
        if (Input.GetMouseButtonDown(0)) down = Input.mousePosition;
        if (!Input.GetMouseButtonUp(0) || (Input.mousePosition - down).sqrMagnitude > 25f) return;   // a drag, not a click
        var cam = Camera.main;
        if (cam != null && Physics.Raycast(cam.ScreenPointToRay(Input.mousePosition), out var hit, 5000f))
        {
            picked = hit.collider.GetComponentInParent<TwinState>();
            if (picked != null) SelectTwin(picked.name);
        }
        else picked = null;
    }

    void OnGUI()
    {
        if (box == null)
        {
            box = new GUIStyle(GUI.skin.box) { font = font, fontSize = 13, alignment = TextAnchor.UpperLeft, wordWrap = true };
            box.normal.textColor = Color.white;
            head = new GUIStyle(box) { fontSize = 15, fontStyle = FontStyle.Bold };
        }
        if (TwinState.LastAnyUpdate < 0f)
        {
            GUI.Box(new Rect(12, 12, 460, 46), "Ожидание данных из Grafana: панель отправляет их\nпри каждом обновлении дашборда (раз в 5 с).", box);
            return;
        }
        var hud = TwinLabel.Format("{complex.sim_clock} · сутки {complex.sim_day:N0} · режим: {complex.mode}\n"
            + "медь {complex.copper_tph:N2} т/ч, за сутки {complex.copper_today:N1} т · "
            + "подстанция {substation.load:N1} из {substation.limit:N0} МВт\nсценарии: {complex.scenarios_text}");
        GUI.Box(new Rect(Screen.width - 452, 12, 440, box.CalcHeight(new GUIContent(hud), 440)), hud, box);
        if (picked == null) return;
        var lines = picked.All
            .Where(kv => !kv.Key.EndsWith("events") && !kv.Key.EndsWith("advice") && !kv.Key.EndsWith("schedule") && !kv.Key.EndsWith("setpoint"))
            .OrderBy(kv => kv.Key)
            .Select(kv => $"{kv.Key} = {Value(kv.Value)}").ToList();
        float h = 34 + 18 * lines.Count;
        GUI.Box(new Rect(12, 12, 340, h), "", box);
        GUI.Label(new Rect(20, 16, 330, 22), picked.name, head);
        GUI.Label(new Rect(20, 40, 330, h - 30), string.Join("\n", lines), box);
    }

    static string Value(Newtonsoft.Json.Linq.JToken v)
    {
        if (v.Type == Newtonsoft.Json.Linq.JTokenType.Float || v.Type == Newtonsoft.Json.Linq.JTokenType.Integer)
            return ((double)v).ToString("N2", TwinLabel.Ru);
        var s = TwinLabel.Word(v.ToString());
        return s.Length > 40 ? s.Substring(0, 40) + "…" : s;
    }
}
