#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform float uIntensity;    // 0-1, leak opacity
uniform float uAngle;        // 0-360, leak direction
uniform vec3 uLeakColor;     // light leak color (warm orange default)
uniform float uWidth;        // 0.05-0.5, band width


out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 base = texture(uTexture, uv);

    float angleRad = uAngle * 3.14159265 / 180.0;
    vec2 dir = vec2(cos(angleRad), sin(angleRad));

    // Animated light band sweeping across screen
    float pos = dot(uv, dir);
    float animPos = fract(pos + uTime * 0.3);
    float leak = exp(-animPos * animPos / (uWidth * uWidth));
    leak += exp(-(1.0 - animPos) * (1.0 - animPos) / (uWidth * uWidth * 0.5)) * 0.3;

    leak *= uIntensity;

    // Screen blend the leak
    vec3 result = base.rgb + uLeakColor * leak;
    result = clamp(result, 0.0, 1.0);

    fragColor = vec4(result, base.a);
}
