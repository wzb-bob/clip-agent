#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uProgress;     // 0-1 normalize time
uniform float uRampPoint;    // 0-1 where the speed change happens
uniform float uSpeedRatio;   // >1 = slow motion after ramp, <1 = fast motion
uniform float uMotionBlur;   // 0-1 blur amount
uniform float uSamples;        // motion blur sample count (2-16)


out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    // Warp the UV coordinate based on time
    // Before rampPoint: normal speed, after: speedRatio
    float warpedProgress;
    if (uProgress <= uRampPoint) {
        warpedProgress = uProgress;
    } else {
        float postRamp = (uProgress - uRampPoint) / (1.0 - uRampPoint);
        warpedProgress = uRampPoint + postRamp * uSpeedRatio;
    }

    // Motion blur: sample along time axis (simulated via offset)
    if (uMotionBlur > 0.01 && uSamples > 1) {
        vec4 accum = vec4(0.0);
        float totalWeight = 0.0;

        for (int i = 0; i < 16; i++) {
            if (i >= uSamples) break;
            float t = (float(i) / float(uSamples - 1.0) - 0.5) * uMotionBlur;
            vec2 offset = vec2(t * 0.02, 0.0); // horizontal motion blur
            accum += texture(uTexture, uv + offset);
            totalWeight += 1.0;
        }
        color = accum / totalWeight;
    }

    // Pulsing edge indicator for ramp point
    float rampDist = abs(uProgress - uRampPoint);
    float edgeGlow = exp(-rampDist * 20.0) * 0.3;
    color.rgb += edgeGlow * vec3(0.8, 0.2, 0.2);

    fragColor = color;
}
