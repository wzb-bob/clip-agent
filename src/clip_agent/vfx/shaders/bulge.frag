#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uRadius;      // 0.05-1
uniform float uStrength;    // 0-1
uniform float uCenterX;    // 0-1
uniform float uCenterY;    // 0-1


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(uCenterX, uCenterY);

    vec2 delta = uv - center;
    float dist = length(delta);

    float bulge = 1.0 + uStrength * (1.0 - smoothstep(0.0, uRadius, dist)) * 0.5;
    vec2 sampleUV = center + delta / bulge;
    sampleUV = clamp(sampleUV, 0.0, 1.0);

    fragColor = texture(uTexture, sampleUV);
}
