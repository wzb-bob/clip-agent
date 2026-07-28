#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uFocusY;
uniform float uFocusHeight;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    float dist = abs(uv.y - uFocusY) / (uFocusHeight * 0.5 + 0.001);
    float blurAmount = smoothstep(0.3, 1.0, dist) * uIntensity * 10.0;

    vec2 texel = 1.0 / uResolution;
    vec4 color = vec4(0.0);
    int samples = int(clamp(blurAmount, 0.0, 10.0));
    float weight = 0.0;

    for (int x = -5; x <= 5; x++) {
        for (int y = -5; y <= 5; y++) {
            float r = length(vec2(float(x), float(y)));
            if (r > float(samples)) continue;
            float w = exp(-r * r / (2.0 * float(samples) * float(samples) * 0.25));
            color += texture(uTexture, uv + vec2(float(x), float(y)) * texel) * w;
            weight += w;
        }
    }

    if (weight > 0.0) color /= weight;
    fragColor = vec4(color.rgb, texture(uTexture, uv).a);
}
