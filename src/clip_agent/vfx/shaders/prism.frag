#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uAngle;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(0.5);
    vec2 dir = uv - center;
    float dist = length(dir);

    float angle = uAngle * 3.14159 / 180.0;
    vec2 dispersion = vec2(cos(angle), sin(angle)) * dist * uIntensity * 0.03;

    float r = texture(uTexture, uv + dispersion * 1.5).r;
    float g = texture(uTexture, uv).g;
    float b = texture(uTexture, uv - dispersion * 1.5).b;

    fragColor = vec4(r, g, b, 1.0);
}
