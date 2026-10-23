// Haul trucks of one face: about one truck per 420 t/h of its shovel's rate
// drive the haul road, loaded up to the crusher and empty back down.

using UnityEngine;

public class TruckFleet : MonoBehaviour
{
    public string shovel = "shovel-1";
    public Vector3[] road;            // from the face up to the crusher
    public Transform[] trucks;
    public GameObject[] loads;        // the ore in each truck's body
    public float tphPerTruck = 420f;
    public float speed = 0.035f;      // road lengths per second

    float[] u;
    float[] cumulative;
    float length;

    public int Active
    {
        get
        {
            var s = TwinState.Get(shovel);
            return s == null ? 0 : Mathf.Min(trucks.Length, Mathf.CeilToInt(s.Num("rate") / tphPerTruck));
        }
    }

    void Start()
    {
        u = new float[trucks.Length];
        for (int i = 0; i < u.Length; i++) u[i] = 2f * i / trucks.Length;
        cumulative = new float[road.Length];
        for (int i = 1; i < road.Length; i++) cumulative[i] = cumulative[i - 1] + Vector3.Distance(road[i - 1], road[i]);
        length = Mathf.Max(cumulative[cumulative.Length - 1], 0.01f);
    }

    void Update()
    {
        int active = Active;
        for (int i = 0; i < trucks.Length; i++)
        {
            bool on = i < active;
            if (trucks[i].gameObject.activeSelf != on) trucks[i].gameObject.SetActive(on);
            if (!on) continue;
            u[i] = (u[i] + Time.deltaTime * speed) % 2f;
            bool back = u[i] > 1f;
            float t = back ? 2f - u[i] : u[i];
            var p = At(t);
            var ahead = At(Mathf.Clamp01(back ? t - 0.01f : t + 0.01f));
            trucks[i].position = p;
            var dir = ahead - p;
            dir.y = 0f;
            if (dir.sqrMagnitude > 1e-6f) trucks[i].rotation = Quaternion.LookRotation(dir);
            if (loads[i] != null) loads[i].SetActive(!back);
        }
    }

    Vector3 At(float t)
    {
        float d = t * length;
        for (int i = 1; i < road.Length; i++)
            if (d <= cumulative[i])
                return Vector3.Lerp(road[i - 1], road[i], Mathf.InverseLerp(cumulative[i - 1], cumulative[i], d));
        return road[road.Length - 1];
    }
}
