#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uTime;


out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    // Horizontal scanline distortion
    float distortion = sin(uv.y * 200.0 + uTime * 5.0) * 0.005 * uIntensity;
    uv.x += distortion;

    // Vertical rolling bar
    float bar = sin((uv.y - uTime * 0.5) * 30.0) * 0.5 + 0.5;
    bar = smoothstep(0.9, 1.0, bar) * 0.3 * uIntensity;

    // Color fringing
    float r = texture(uTexture, uv + vec2(0.002 * uIntensity, 0.0)).r;
    float g = texture(uTexture, uv).g;
    float b = texture(uTexture, uv - vec2(0.002 * uIntensity, 0.0)).b;

    vec3 color = vec3(r, g, b);
    color -= bar;

    fragColor = vec4(color, 1.0);
}
