#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform float uAmplitude;   // 0-20 pixels
uniform float uFrequency;   // 1-30 ripple count
uniform float uSpeed;       // 0-10 expansion speed


out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(0.5, 0.5);

    float dist = length(uv - center) * uResolution.y;

    float ripple = sin(dist * uFrequency * 0.1 - uTime * uSpeed * 3.0);
    float falloff = exp(-dist * 0.002);
    float displacement = ripple * falloff * uAmplitude;

    vec2 dir = normalize(uv - center + 0.0001);
    vec2 sampleUV = uv + dir * displacement / uResolution;

    sampleUV = clamp(sampleUV, 0.0, 1.0);
    fragColor = texture(uTexture, sampleUV);
}
