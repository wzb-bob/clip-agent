#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uIntensity;
uniform float uAngle;
uniform float uFalloff;
uniform float uTime;

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    vec2 center = uv - 0.5;
    float dist = length(center);
    float falloff = 1.0 + dist * uFalloff;

    vec2 offset = vec2(cos(uAngle), sin(uAngle)) * uIntensity / uResolution * falloff;

    float r = texture(uTexture, uv + offset).r;
    float g = texture(uTexture, uv).g;
    float b = texture(uTexture, uv - offset).b;
    float a = texture(uTexture, uv).a;

    fragColor = vec4(r, g, b, a);
}
