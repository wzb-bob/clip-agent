#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uAmount;
uniform float uWaveAmp;
uniform float uWaveFreq;
uniform float uNoiseAmount;
uniform float uTime;

out vec4 fragColor;

float random(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    float wave = sin(uv.y * uWaveFreq * 10.0 + uTime * 3.0) * uWaveAmp / uResolution.x;
    float noise = (random(uv * 100.0 + uTime) - 0.5) * uNoiseAmount * 2.0 / uResolution.x;

    vec2 offset = vec2(wave + noise + uAmount / uResolution.x, 0.0);

    float r = texture(uTexture, uv + offset).r;
    float g = texture(uTexture, uv).g;
    float b = texture(uTexture, uv - offset).b;
    float a = texture(uTexture, uv).a;

    fragColor = vec4(r, g, b, a);
}
