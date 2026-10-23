// Orbit the scene with the left mouse button, pan with the right, zoom with
// the wheel, as on the 3D page. The build must not swallow the keyboard of
// the Grafana dashboard around it (OpenEgiz Unity contract).

using UnityEngine;

public class OrbitCamera : MonoBehaviour
{
    public Vector3 target = new Vector3(20f, 0f, -30f);
    public float distance = 420f;
    public float yaw = 0f, pitch = 39f;
    public float minDistance = 60f, maxDistance = 900f;

    void Awake()
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        WebGLInput.captureAllKeyboardInput = false;
#endif
        Apply();
    }

    void LateUpdate()
    {
        // the frame of the press carries the jump of the pointer since the last frame, not a drag
        if (Input.GetMouseButton(0) && !Input.GetMouseButtonDown(0))
        {
            yaw += Input.GetAxis("Mouse X") * 4f;
            pitch = Mathf.Clamp(pitch - Input.GetAxis("Mouse Y") * 3f, 8f, 85f);
        }
        if (Input.GetMouseButton(1) && !Input.GetMouseButtonDown(1))
        {
            var right = transform.right; right.y = 0f;
            var fwd = Vector3.Cross(right, Vector3.up);
            target -= (right * Input.GetAxis("Mouse X") + fwd * Input.GetAxis("Mouse Y")) * distance * 0.01f;
        }
        float wheel = Input.mouseScrollDelta.y;
        if (Mathf.Abs(wheel) > 0.01f) distance = Mathf.Clamp(distance * (1f - wheel * 0.08f), minDistance, maxDistance);
        Apply();
    }

    void Apply()
    {
        var rot = Quaternion.Euler(pitch, yaw, 0f);
        transform.position = target - rot * Vector3.forward * distance;
        transform.rotation = rot;
    }
}
