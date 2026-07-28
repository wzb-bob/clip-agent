#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform sampler2D uFromTexture;
uniform vec2 uResolution;
uniform float uProgress;
uniform float uSmoothness;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 from = texture(uFromTexture, uv);
    vec4 to = texture(uTexture, uv);
    float t = smoothstep(0.0, uSmoothness, uProgress);
    t = smoothstep(t - uSmoothness * 0.5, t + uSmoothness * 0.5, uProgress);
    fragColor = mix(from, to, t);
}
