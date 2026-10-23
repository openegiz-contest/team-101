// A label over an object: a title and a line of values from the twins.
// The template refers to features as {twin.feature} or {twin.feature:N1},
// for example "{mill-1.feed:N0} т/ч · {mill-1.state}". State words from the
// simulator are shown in Russian.

using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;
using UnityEngine;

public class TwinLabel : MonoBehaviour
{
    public string title;
    [TextArea] public string template;
    public TextMesh text;
    public TextMesh shadow;           // the same text, dark and a little behind, for contrast

    // Russian number format without relying on culture data in the WebGL player: 1 558,4
    public static readonly NumberFormatInfo Ru = new NumberFormatInfo { NumberGroupSeparator = " ", NumberDecimalSeparator = "," };
    static readonly Regex Field = new Regex(@"\{([a-z0-9-]+)\.([a-z0-9_]+)(?::([A-Z][0-9]?))?\}");
    static readonly Dictionary<string, string> Words = new Dictionary<string, string>
    {
        { "running", "работает" }, { "repair", "РЕМОНТ" }, { "tripped", "ОТКЛЮЧЕНА САОН" },
        { "normal", "обычный" }, { "high-density", "высокоплотный" },
        { "digging", "копает" }, { "standby", "ожидает" }, { "idle", "стоит" },
        { "optimizer", "план оптимизатора" }, { "departments", "каждый отдел сам" },
        { "True", "да" }, { "False", "нет" }, { "true", "да" }, { "false", "нет" },
    };

    float next;

    void LateUpdate()
    {
        var cam = Camera.main;
        if (cam != null) transform.rotation = cam.transform.rotation;
        if (Time.time < next) return;
        next = Time.time + 0.5f;
        text.text = string.IsNullOrEmpty(template) ? title : title + "\n" + Format(template);
        if (shadow != null) shadow.text = text.text;
    }

    public static string Format(string template) => Field.Replace(template, m =>
    {
        var s = TwinState.Get(m.Groups[1].Value);
        var feature = m.Groups[2].Value;
        if (s == null || !s.Has(feature)) return "–";
        if (m.Groups[3].Success) return s.Num(feature).ToString(m.Groups[3].Value, Ru);
        return Word(s.Str(feature));
    });

    public static string Word(string raw) => Words.TryGetValue(raw, out var w) ? w : raw;
}
