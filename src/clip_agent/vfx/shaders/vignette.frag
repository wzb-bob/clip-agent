#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uAmount;
uniform float uFeather;
uniform float uRoundness;
uniform float uTime;

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    vec2 center = uv - 0.5;
    vec2 dist = center * vec2(1.0, mix(1.0, uRoundness, 0.5));
    float vignette = 1.0 - dot(dist, dist);
    vignette = smoothstep(1.0 - uAmount, 1.0 - uAmount + uFeather, vignette);

    vec4 color = texture(uTexture, uv);
    fragColor = vec4(color.rgb * vignette, color.a);
}
