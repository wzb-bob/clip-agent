#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform vec4 uCurveR;   // x=shadows, y=midLow, z=midHigh, w=highlights
uniform vec4 uCurveG;
uniform vec4 uCurveB;
uniform vec4 uCurveA;   // master/alpha curve
uniform float uBlend;   // 0-1 mix with original


float applyCurve(float x, vec4 points) {
    // Catmull-Rom spline through 4 control points at positions 0, 0.33, 0.66, 1.0
    float t = x;
    float t0 = 0.0, t1 = 0.33, t2 = 0.66, t3 = 1.0;
    float p0 = points.x, p1 = points.y, p2 = points.z, p3 = points.w;

    // Cubic hermite interpolation between p1 and p2
    if (t <= t0) return p0;
    if (t >= t3) return p3;
    if (t <= t1) {
        float a = (t - t0) / (t1 - t0);
        return mix(p0, p1, smoothstep(0.0, 1.0, a));
    }
    if (t >= t2) {
        float a = (t - t2) / (t3 - t2);
        return mix(p2, p3, smoothstep(0.0, 1.0, a));
    }
    float a = (t - t1) / (t2 - t1);
    float m0 = (p1 - p0) / (t1 - t0) * (t2 - t1);
    float m1 = (p3 - p2) / (t3 - t2) * (t2 - t1);
    float a2 = a * a;
    float a3 = a2 * a;
    return (2.0 * a3 - 3.0 * a2 + 1.0) * p1
         + (a3 - 2.0 * a2 + a) * m0
         + (-2.0 * a3 + 3.0 * a2) * p2
         + (a3 - a2) * m1;
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    float r = applyCurve(color.r, uCurveR);
    float g = applyCurve(color.g, uCurveG);
    float b = applyCurve(color.b, uCurveB);

    vec3 curved = vec3(r, g, b);
    vec3 result = mix(color.rgb, curved, uBlend);

    fragColor = vec4(result, color.a);
}
