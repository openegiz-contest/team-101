// A grinding line: the drum turns with the feed of its mill twin; grey when
// under repair, flashing red when tripped by load shedding.

using UnityEngine;

public class MillDrum : MonoBehaviour
{
    public string twin = "mill-1";
    public Transform drum;
    public Renderer[] shells;
    public Color running = new Color(0.31f, 0.56f, 0.66f);
    public Color repair = new Color(0.43f, 0.43f, 0.43f);
    public Color tripped = new Color(0.70f, 0.23f, 0.21f);

    void Update()
    {
        var s = TwinState.Get(twin);
        if (s == null) return;
        var state = s.Str("state", "running");
        float speed = state == "running" ? 0.4f + 0.6f * s.Num("feed") / 1600f : 0f;
        drum.Rotate(Vector3.right, speed * 90f * Time.deltaTime, Space.Self);
        var c = state == "running" ? running : state == "repair" ? repair
            : Color.Lerp(tripped, Color.black, 0.5f + 0.5f * Mathf.Sin(Time.time * 6f));
        foreach (var r in shells) r.material.color = c;
    }
}
