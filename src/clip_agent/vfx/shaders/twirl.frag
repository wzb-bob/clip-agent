#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uAngle;       // -360 to 360 degrees
uniform float uRadius;       // 0.1-1.5


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(0.5, 0.5);

    vec2 delta = uv - center;
    float dist = length(delta);
    float maxDist = uRadius * 1.414;

    float angle = uAngle * 3.14159265 / 180.0;
    float twirl = angle * (1.0 - smoothstep(0.0, maxDist, dist));

    float c = cos(twirl);
    float s = sin(twirl);
    vec2 rotated = vec2(delta.x * c - delta.y * s, delta.x * s + delta.y * c);

    vec2 sampleUV = center + rotated;
    sampleUV = clamp(sampleUV, 0.0, 1.0);

    fragColor = texture(uTexture, sampleUV);
}
