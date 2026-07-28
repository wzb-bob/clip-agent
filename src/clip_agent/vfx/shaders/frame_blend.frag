#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform sampler2D uPrevTexture; // previous frame
uniform float uBlendFactor;      // 0-1, weight of previous frame
uniform float uFrameCount;         // number of frames to blend
uniform float uFrameWeight;      // exponential decay per older frame


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 current = texture(uTexture, uv);
    vec4 previous = texture(uPrevTexture, uv);

    // Weighted blend: current frame + weighted previous frame
    vec4 blended = mix(current, previous, uBlendFactor);

    // Adaptive blend: reduce ghosting in high-motion areas
    float motionDiff = length(current.rgb - previous.rgb);
    float adaptiveWeight = mix(uBlendFactor, 0.0, smoothstep(0.05, 0.2, motionDiff));
    vec4 adaptive = mix(current, previous, adaptiveWeight);

    // Mix between uniform and adaptive blending
    fragColor = mix(blended, adaptive, 0.5);
}
