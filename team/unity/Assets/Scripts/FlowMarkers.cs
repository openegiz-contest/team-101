// A flow of ore, water, power or concentrate: markers move along a path; how
// many are visible and how fast they go follow a twin value / max.

using UnityEngine;

public class FlowMarkers : MonoBehaviour
{
    public string twin;
    public string feature;
    public float max = 1f;
    public Vector3[] path;
    public Transform[] markers;
    public float speed = 6f;          // world units per second at full rate

    float[] cumulative;
    float length, offset;

    void Start()
    {
        cumulative = new float[path.Length];
        for (int i = 1; i < path.Length; i++) cumulative[i] = cumulative[i - 1] + Vector3.Distance(path[i - 1], path[i]);
        length = Mathf.Max(cumulative[cumulative.Length - 1], 0.01f);
        offset = Random.value * length;
    }

    public float Rate
    {
        get
        {
            var s = TwinState.Get(twin);
            return s == null ? 0f : Mathf.Clamp01(s.Num(feature) / max);
        }
    }

    void Update()
    {
        float rate = Rate;
        int n = Mathf.RoundToInt(markers.Length * rate);
        offset = (offset + Time.deltaTime * speed * (0.4f + rate)) % length;
        for (int i = 0; i < markers.Length; i++)
        {
            bool on = i < n;
            if (markers[i].gameObject.activeSelf != on) markers[i].gameObject.SetActive(on);
            if (on) markers[i].position = At((offset + length * i / Mathf.Max(n, 1)) % length);
        }
    }

    Vector3 At(float d)
    {
        for (int i = 1; i < path.Length; i++)
            if (d <= cumulative[i])
                return Vector3.Lerp(path[i - 1], path[i], Mathf.InverseLerp(cumulative[i - 1], cumulative[i], d));
        return path[path.Length - 1];
    }
}
