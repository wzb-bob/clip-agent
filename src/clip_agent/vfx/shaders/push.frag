#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform sampler2D uFromTexture;
uniform vec2 uResolution;
uniform float uProgress;
uniform float uDirection; // 0=right, 1=left, 2=up, 3=down


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 offset = vec2(0.0);

    if (uDirection < 0.5) offset = vec2(-1.0 + uProgress, 0.0);
    else if (uDirection < 1.5) offset = vec2(1.0 - uProgress, 0.0);
    else if (uDirection < 2.5) offset = vec2(0.0, -1.0 + uProgress);
    else offset = vec2(0.0, 1.0 - uProgress);

    vec2 fromUV = uv + offset;
    vec2 toUV = uv + offset + vec2(sign(offset.x), sign(offset.y));

    vec4 fromColor = texture(uFromTexture, fromUV);
    vec4 toColor = texture(uTexture, toUV);

    float mask = step(0.0, fromUV.x) * step(fromUV.x, 1.0) * step(0.0, fromUV.y) * step(fromUV.y, 1.0);
    fragColor = mix(toColor, fromColor, mask);
}
