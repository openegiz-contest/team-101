// Sizes an object by a twin value, as the 3D page does: a stockpile cone by
// the cube root of its tonnage, the process water by the tank level, the
// pond by the square root of its area.

using UnityEngine;

public class ScaleByFeature : MonoBehaviour
{
    public enum Mode { CubeRootUniform, HeightFromBase, SqrtFlat }

    public string twin;
    public string feature;
    public Mode mode;
    public float factor = 1f;         // value -> size
    public float min = 0.1f;
    public float max = 1000f;

    Vector3 baseScale;
    Vector3 basePos;

    void Awake() { baseScale = transform.localScale; basePos = transform.localPosition; }

    void Update()
    {
        var s = TwinState.Get(twin);
        if (s == null || !s.Has(feature)) return;
        float v = s.Num(feature);
        switch (mode)
        {
            case Mode.CubeRootUniform:
            {
                float k = Mathf.Clamp(Mathf.Pow(Mathf.Max(v, 0f) * factor, 1f / 3f), min, max);
                transform.localScale = baseScale * k;
                transform.localPosition = basePos + Vector3.up * (k * baseScale.y / 2f);
                break;
            }
            case Mode.HeightFromBase:
            {
                float h = Mathf.Clamp(v * factor, min, max);
                transform.localScale = new Vector3(baseScale.x, h, baseScale.z);
                transform.localPosition = basePos + Vector3.up * (h / 2f);
                break;
            }
            case Mode.SqrtFlat:
            {
                float r = Mathf.Clamp(Mathf.Sqrt(Mathf.Max(v, 0f)) * factor, min, max);
                transform.localScale = new Vector3(r, baseScale.y, r);
                break;
            }
        }
    }
}
