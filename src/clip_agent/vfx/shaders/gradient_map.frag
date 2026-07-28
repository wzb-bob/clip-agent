#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform vec3 uColorA;       // shadow color (dark)
uniform vec3 uColorB;       // highlight color (bright)
uniform float uBlend;       // 0-1 mix with original


float luminance(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    float lum = luminance(color.rgb);
    vec3 mapped = mix(uColorA, uColorB, lum);

    vec3 result = mix(color.rgb, mapped, uBlend);
    fragColor = vec4(result, color.a);
}
