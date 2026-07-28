#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uLevels;       // 2-32, number of color levels per channel


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    float levels = max(uLevels, 2.0);
    color.rgb = floor(color.rgb * levels) / (levels - 1.0);

    fragColor = color;
}
