#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uCenter;       // 0-1, mirror axis position
uniform float uAngle;        // 0-360, mirror axis angle
uniform float uHorizontal;    // true=horizontal mirror, false=vertical


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    float reflectPos;
    if (uHorizontal > 0.5) {
        reflectPos = uv.x > uCenter ? 2.0 * uCenter - uv.x : uv.x;
        reflectPos = clamp(reflectPos, 0.0, 1.0);
        uv = vec2(reflectPos, uv.y);
    } else {
        reflectPos = uv.y > uCenter ? 2.0 * uCenter - uv.y : uv.y;
        reflectPos = clamp(reflectPos, 0.0, 1.0);
        uv = vec2(uv.x, reflectPos);
    }

    fragColor = texture(uTexture, uv);
}
