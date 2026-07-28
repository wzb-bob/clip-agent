#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform float uAmplitude;   // 0-50, wave height in pixels
uniform float uFrequency;   // 0.5-10, wave count
uniform float uSpeed;       // 0-5, animation speed


out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    float wave = sin(uv.y * uFrequency * 20.0 + uTime * uSpeed * 3.0) * uAmplitude / uResolution.x;
    wave += sin(uv.x * uFrequency * 15.0 + uTime * uSpeed * 2.5) * uAmplitude * 0.3 / uResolution.y;

    vec2 distortedUV = uv + vec2(wave, 0.0);
    distortedUV = clamp(distortedUV, 0.0, 1.0);

    fragColor = texture(uTexture, distortedUV);
}
