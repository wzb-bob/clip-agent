#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform sampler2D uFromTexture;
uniform vec2 uResolution;
uniform float uProgress;
uniform float uCenterX;
uniform float uCenterY;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(uCenterX, uCenterY);
    vec2 dir = uv - center;
    float angle = atan(dir.y, dir.x) + 3.14159;
    float normalized = angle / (2.0 * 3.14159);

    float mask = step(normalized, uProgress);
    fragColor = mix(texture(uFromTexture, uv), texture(uTexture, uv), mask);
}
