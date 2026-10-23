// Pulses amber on the objects of the twins the planner names as the
// bottleneck of the current hour (planner.bottleneck_twins).

using UnityEngine;

public class Bottleneck : MonoBehaviour
{
    public string twin;
    public Renderer[] renderers;

    static readonly Color Amber = new Color(0.6f, 0.33f, 0.02f);
    bool lit;

    void Update()
    {
        var planner = TwinState.Get("planner");
        bool on = planner != null && ("," + planner.Str("bottleneck_twins") + ",").Contains("," + twin + ",");
        if (!on && !lit) return;
        var c = on ? Amber * (0.5f + 0.5f * Mathf.Sin(Time.time * 5f)) : Color.black;
        foreach (var r in renderers)
        {
            r.material.EnableKeyword("_EMISSION");
            r.material.SetColor("_EmissionColor", c);
        }
        lit = on;
    }
}
