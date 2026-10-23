// The state of one twin of the complex, as the Grafana Unity panel sends it.
//
// The panel groups its query rows by the `thingId` column and calls
// SendMessage(thingId, "SetValues", json) on the GameObject with that exact
// name, for example "kz.limit:mill-1". The json is {"series": {...}} with one
// key per InfluxDB field, "value_<feature>_properties_value", or
// {"series": [{...}, ...]} when the queries return several rows for the twin.
// Here every value is filed under its feature name: "feed", "state", ...

using System.Collections.Generic;
using System.Globalization;
using Newtonsoft.Json.Linq;
using UnityEngine;

public class TwinState : MonoBehaviour
{
    const string Prefix = "value_", Suffix = "_properties_value";
    static readonly Dictionary<string, TwinState> byName = new Dictionary<string, TwinState>();

    readonly Dictionary<string, JToken> values = new Dictionary<string, JToken>();

    /// <summary>Twin name without the namespace: "mill-1".</summary>
    public string Twin => name.Substring(name.IndexOf(':') + 1);
    public float LastUpdate { get; private set; } = -1f;
    public static float LastAnyUpdate { get; private set; } = -1f;

    void Awake() => byName[Twin] = this;
    void OnDestroy() => byName.Remove(Twin);

    public static TwinState Get(string twin) => byName.TryGetValue(twin, out var s) ? s : null;

    // Called by the Grafana Unity panel.
    public void SetValues(string json)
    {
        JToken series;
        try { series = JObject.Parse(json)["series"]; }
        catch (System.Exception e) { Debug.LogWarning($"{name}: bad SetValues payload: {e.Message}"); return; }
        if (series is JArray rows) foreach (var row in rows) Store(row as JObject);
        else Store(series as JObject);
        LastUpdate = LastAnyUpdate = Time.time;
    }

    void Store(JObject row)
    {
        if (row == null) return;
        foreach (var p in row.Properties())
        {
            if (!p.Name.StartsWith(Prefix) || !p.Name.EndsWith(Suffix)) continue;
            if (p.Value.Type == JTokenType.Null) continue;
            values[p.Name.Substring(Prefix.Length, p.Name.Length - Prefix.Length - Suffix.Length)] = p.Value;
        }
    }

    public bool Has(string feature) => values.ContainsKey(feature);

    public float Num(string feature, float fallback = 0f)
    {
        if (!values.TryGetValue(feature, out var v)) return fallback;
        switch (v.Type)
        {
            case JTokenType.Integer:
            case JTokenType.Float: return v.Value<float>();
            case JTokenType.Boolean: return v.Value<bool>() ? 1f : 0f;
            case JTokenType.String:
                return float.TryParse(v.Value<string>(), NumberStyles.Float, CultureInfo.InvariantCulture, out var f) ? f : fallback;
            default: return fallback;
        }
    }

    public string Str(string feature, string fallback = "")
        => values.TryGetValue(feature, out var v) && v.Type != JTokenType.Null ? v.ToString() : fallback;

    public bool Bool(string feature) => values.TryGetValue(feature, out var v)
        && (v.Type == JTokenType.Boolean ? v.Value<bool>() : v.ToString() == "true" || v.ToString() == "1");

    /// <summary>All values, for the info card: "feed = 1 558".</summary>
    public IEnumerable<KeyValuePair<string, JToken>> All => values;
}
