#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;   // 0-1
uniform float uSourceX;     // 0-1 light source position
uniform float uSourceY;     // 0-1


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 base = texture(uTexture, uv);

    vec2 source = vec2(uSourceX, uSourceY);
    vec2 dir = uv - source;
    float dist = length(dir);

    // Main flare bright spot
    float flare1 = exp(-dist * dist * 80.0) * 0.8;

    // Secondary ring
    float ringDist = abs(dist - 0.05);
    float ring = exp(-ringDist * ringDist * 500.0) * 0.3;

    // Anamorphic streak
    float streak = exp(-abs(dir.x) * 30.0) * exp(-dist * 1.5) * 0.4;

    // Ghost reflections (opposite side of center from source)
    vec2 ghostPos = 0.5 - (source - 0.5);
    float ghostDist = length(uv - ghostPos);
    float ghost = exp(-ghostDist * ghostDist * 40.0) * 0.15;

    float flare = (flare1 + ring + streak + ghost) * uIntensity;
    vec3 flareColor = vec3(0.9, 0.85 + flare * 0.15, 0.7);

    // Screen blend
    vec3 result = base.rgb + flareColor * flare;
    result = clamp(result, 0.0, 1.0);

    fragColor = vec4(result, base.a);
}
