#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uProgress;    // 0-1
uniform float uAngle;       // 0-360 degrees
uniform float uFeather;     // 0-0.3


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    float angleRad = uAngle * 3.14159265 / 180.0;
    vec2 dir = vec2(cos(angleRad), sin(angleRad));

    float dist = dot(uv - 0.5, dir) + 0.5;
    float alpha = smoothstep(uProgress - uFeather, uProgress + uFeather, dist);

    fragColor = texture(uTexture, uv) * alpha;
}
