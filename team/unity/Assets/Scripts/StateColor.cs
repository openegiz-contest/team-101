// Colours renderers by a twin value: a face with hard ore, a thickener in
// high-density mode, the process water tank below the interlock level, a
// pipe or power line near its limit.

using UnityEngine;

public class StateColor : MonoBehaviour
{
    public enum Rule { BoolTrue, StringEquals, BelowValue, RatioAbove }

    public string twin;
    public string feature;
    public Rule rule;
    public string equals;             // StringEquals
    public float threshold;           // BelowValue, RatioAbove
    public string limitFeature;       // RatioAbove: feature / limitFeature
    public Color normal = Color.white;
    public Color alert = Color.red;
    public Renderer[] renderers;

    void Update()
    {
        var s = TwinState.Get(twin);
        if (s == null || !s.Has(feature)) return;
        bool on = false;
        switch (rule)
        {
            case Rule.BoolTrue: on = s.Bool(feature); break;
            case Rule.StringEquals: on = s.Str(feature) == equals; break;
            case Rule.BelowValue: on = s.Num(feature) < threshold; break;
            case Rule.RatioAbove:
                float lim = s.Num(limitFeature, 0f);
                on = lim > 0f && s.Num(feature) / lim >= threshold;
                break;
        }
        var c = on ? alert : normal;
        foreach (var r in renderers) r.material.color = c;
    }
}
