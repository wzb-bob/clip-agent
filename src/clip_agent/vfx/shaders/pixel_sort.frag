#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uThreshold;    // 0-1, luminance trigger for sorting
uniform float uStrength;     // 0-1, sort displacement strength
uniform float uHorizontal;     // sort direction


float luminance(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 texel = 1.0 / uResolution;

    float centerLum = luminance(texture(uTexture, uv).rgb);

    // Search along axis for pixels to "pull"
    vec3 accumulated = vec3(0.0);
    float count = 0.0;

    int searchRange = int(uStrength * 50.0);

    for (int i = -25; i <= 25; i++) {
        if (abs(i) > searchRange) continue;

        vec2 sampleUV = uHorizontal > 0.5
            ? uv + vec2(float(i) * texel.x, 0.0)
            : uv + vec2(0.0, float(i) * texel.y);

        sampleUV = clamp(sampleUV, 0.0, 1.0);
        vec3 sampleColor = texture(uTexture, sampleUV).rgb;
        float sampleLum = luminance(sampleColor);

        if (sampleLum > uThreshold) {
            accumulated += sampleColor;
            count += 1.0;
        }
    }

    if (count > 0.0) {
        fragColor = vec4(accumulated / count, 1.0);
    } else {
        fragColor = texture(uTexture, uv);
    }
}
