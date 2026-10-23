// Time of day of the model (complex.sim_hour) sets the sun and the sky,
// like the 3D page.

using UnityEngine;

public class SkyClock : MonoBehaviour
{
    public Light sun;
    public Camera cam;

    static readonly Color Day = new Color(0.61f, 0.76f, 0.85f);
    static readonly Color Dusk = new Color(0.24f, 0.29f, 0.40f);
    static readonly Color Night = new Color(0.06f, 0.10f, 0.16f);

    void Update()
    {
        var s = TwinState.Get("complex");
        if (s == null || !s.Has("sim_hour")) return;
        float h = Mathf.Repeat(s.Num("sim_hour"), 24f);
        Color c; float k;
        if (h >= 7f && h < 18f) { c = Day; k = 1f; }
        else if (h >= 18f && h < 21f) { c = Color.Lerp(Day, Dusk, (h - 18f) / 3f); k = 1f - 0.25f * (h - 18f) / 3f; }
        else if (h >= 21f || h < 5f) { c = Color.Lerp(Dusk, Night, 0.6f); k = 0.72f; }
        else { c = Color.Lerp(Night, Day, (h - 5f) / 2f); k = 0.72f + 0.28f * (h - 5f) / 2f; }
        cam.backgroundColor = c;
        RenderSettings.fogColor = c;
        sun.intensity = 1.1f * k;
        float a = (h - 6f) / 12f * 180f;
        sun.transform.rotation = Quaternion.Euler(Mathf.Clamp(Mathf.Sin(a * Mathf.Deg2Rad) * 70f, 15f, 70f), -60f + a * 0.5f, 0f);
    }
}
