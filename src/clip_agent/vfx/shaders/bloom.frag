#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uThreshold;
uniform float uIntensity;
uniform float uRadius;
uniform float uTime;

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 texelSize = 1.0 / uResolution;

    vec4 baseColor = texture(uTexture, uv);

    float brightness = dot(baseColor.rgb, vec3(0.2126, 0.7152, 0.0722));
    float mask = smoothstep(uThreshold, uThreshold + 0.1, brightness);

    if (mask < 0.01) {
        fragColor = baseColor;
        return;
    }

    vec3 blurColor = vec3(0.0);
    float totalWeight = 0.0;
    float radius = clamp(uRadius, 1.0, 10.0);

    for (int x = -5; x <= 5; x++) {
        for (int y = -5; y <= 5; y++) {
            float dist = length(vec2(float(x), float(y)));
            if (dist > radius) continue;

            vec2 sampleUV = uv + vec2(float(x), float(y)) * texelSize * radius;
            sampleUV = clamp(sampleUV, 0.0, 1.0);

            float weight = exp(-dist * dist / (2.0 * radius * radius * 0.3));
            vec3 sampleColor = texture(uTexture, sampleUV).rgb;
            float sampleBright = dot(sampleColor, vec3(0.2126, 0.7152, 0.0722));
            float sampleMask = smoothstep(uThreshold, uThreshold + 0.1, sampleBright);

            blurColor += sampleColor * weight * sampleMask;
            totalWeight += weight * sampleMask;
        }
    }

    if (totalWeight > 0.0) {
        blurColor /= totalWeight;
    }

    vec3 result = baseColor.rgb + blurColor * uIntensity * mask;
    fragColor = vec4(result, baseColor.a);
}
