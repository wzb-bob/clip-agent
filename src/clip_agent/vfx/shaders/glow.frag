#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uThreshold;    // 0-1, luminance trigger
uniform float uIntensity;    // 0-3, glow strength
uniform float uRadius;       // 1-30, glow spread in pixels
uniform vec3 uTint;          // glow color tint (1,1,1 = neutral)


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 texel = 1.0 / uResolution;
    vec4 base = texture(uTexture, uv);

    float lum = dot(base.rgb, vec3(0.299, 0.587, 0.114));
    float glowMask = smoothstep(uThreshold - 0.1, uThreshold, lum);

    if (glowMask < 0.01) {
        fragColor = base;
        return;
    }

    // Multi-pass directional blur for glow
    vec3 glow = vec3(0.0);
    float totalWeight = 0.0;
    int steps = int(clamp(uRadius / 2.0, 1.0, 15.0));

    for (int i = -steps; i <= steps; i++) {
        for (int j = -steps; j <= steps; j++) {
            vec2 offset = vec2(float(i), float(j)) * texel * uRadius / float(steps);
            vec3 samp = texture(uTexture, uv + offset).rgb;
            float sampleLum = dot(samp, vec3(0.299, 0.587, 0.114));
            float weight = 1.0 - abs(float(i) + float(j)) / (float(steps) * 2.0 + 1.0);
            weight *= smoothstep(uThreshold - 0.1, uThreshold, sampleLum);
            glow += samp * weight;
            totalWeight += weight;
        }
    }

    glow = totalWeight > 0.0 ? glow / totalWeight : vec3(0.0);
    glow *= uTint * uIntensity;

    // Screen/additive blend
    vec3 result = base.rgb + glow * glowMask;
    result = clamp(result, 0.0, 1.0);

    fragColor = vec4(result, base.a);
}
