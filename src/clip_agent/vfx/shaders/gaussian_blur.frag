#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uRadius;
uniform float uTime;

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 texelSize = 1.0 / uResolution;

    vec4 color = vec4(0.0);
    float totalWeight = 0.0;
    float radius = clamp(uRadius, 0.0, 25.0);
    int samples = int(clamp(radius, 1.0, 10.0));

    for (int x = -5; x <= 5; x++) {
        for (int y = -5; y <= 5; y++) {
            float dist = length(vec2(float(x), float(y)));
            if (dist > radius) continue;
            float weight = exp(-dist * dist / (2.0 * radius * radius));
            vec2 sampleUV = uv + vec2(float(x), float(y)) * texelSize * radius;
            sampleUV = clamp(sampleUV, 0.0, 1.0);
            color += texture(uTexture, sampleUV) * weight;
            totalWeight += weight;
        }
    }

    fragColor = totalWeight > 0.0 ? color / totalWeight : texture(uTexture, uv);
}
