#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uIntensity;
uniform float uBlockSize;
uniform float uSpeed;
uniform float uTime;

out vec4 fragColor;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise(vec2 p, float t) {
    return hash(p + floor(t * uSpeed));
}

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    vec2 blockCoord = floor(uv * uResolution / uBlockSize);
    float r = noise(blockCoord, uTime);

    float displace = step(0.85, r) * uIntensity;

    float offsetX = (hash(blockCoord + uTime) - 0.5) * displace * 80.0 / uResolution.x;
    float offsetY = (hash(blockCoord - uTime) - 0.5) * displace * 10.0 / uResolution.y;

    vec2 displacedUV = uv + vec2(offsetX, offsetY);
    displacedUV = clamp(displacedUV, 0.0, 1.0);

    vec4 color = texture(uTexture, displacedUV);
    if (displace > 0.01) {
        color.r = texture(uTexture, displacedUV + vec2(offsetX * 2.0, 0.0)).r;
        color.b = texture(uTexture, displacedUV - vec2(offsetX * 2.0, 0.0)).b;
    }

    fragColor = color;
}
