#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uIntensity;
uniform float uSize;
uniform float uColored;
uniform float uTime;

out vec4 fragColor;

float random(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    vec4 color = texture(uTexture, uv);

    vec2 grainUV = uv * uResolution / uSize;
    float grain = random(grainUV + uTime * 123.456);

    if (uColored > 0.5) {
        float r = random(grainUV + vec2(1.0, 0.0) + uTime * 123.456);
        float g = random(grainUV + vec2(0.0, 1.0) + uTime * 123.456);
        float b = random(grainUV + vec2(1.0, 1.0) + uTime * 123.456);
        color.rgb += (vec3(r, g, b) - 0.5) * uIntensity;
    } else {
        color.rgb += (grain - 0.5) * uIntensity;
    }

    fragColor = clamp(color, 0.0, 1.0);
}
