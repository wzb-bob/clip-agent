#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uThreshold;    // 0-1
uniform float uSoftness;     // 0-0.5, edge softness


float luminance(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);
    float lum = luminance(color.rgb);

    float t = smoothstep(uThreshold - uSoftness, uThreshold + uSoftness, lum);

    fragColor = vec4(vec3(t), color.a);
}
