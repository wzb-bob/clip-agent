#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform float uNoiseAmount;    // 0-1, grain intensity
uniform float uTrackingError;  // 0-1, horizontal line displacement
uniform float uColorBleed;     // 0-1, chroma smearing
uniform float uTapeWrinkle;    // 0-1, vertical tape damage lines


float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float hash12(vec2 p) {
    float h = dot(p, vec2(127.1, 311.7));
    return fract(sin(h) * 43758.5453);
}

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    // Tracking error: shift entire horizontal bands
    float bandY = floor(uv.y * uResolution.y / 8.0);
    float tracking = (hash12(vec2(bandY + floor(uTime * 4.0), 0.0)) - 0.5) * uTrackingError * 0.03;
    uv.x += tracking;

    // Color bleed: smear chroma horizontally
    float bleedOffset = uColorBleed * 0.005;
    float r = texture(uTexture, uv + vec2(bleedOffset, 0.0)).r;
    float g = texture(uTexture, uv).g;
    float b = texture(uTexture, uv - vec2(bleedOffset, 0.0)).b;

    // Film grain
    float grain = (hash(uv * uResolution + uTime * 100.0) - 0.5) * uNoiseAmount;

    // Tape wrinkle lines (vertical opaque bands)
    float wrinkleX = floor(uv.x * uResolution.x / 120.0);
    float wrinkle = 1.0;
    if (hash(vec2(wrinkleX, 0.5)) > (1.0 - uTapeWrinkle * 0.3)) {
        wrinkle = 0.6 + hash(vec2(wrinkleX, uTime)) * 0.4;
    }

    float a = texture(uTexture, uv).a;
    vec3 color = vec3(r, g, b) + grain;
    color *= wrinkle;

    // Slight desaturation
    float lum = dot(color, vec3(0.299, 0.587, 0.114));
    color = mix(color, vec3(lum), 0.15);

    fragColor = vec4(color, a);
}
