#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uRR; uniform float uRG; uniform float uRB;
uniform float uGR; uniform float uGG; uniform float uGB;
uniform float uBR; uniform float uBG; uniform float uBB;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec3 color = texture(uTexture, uv).rgb;

    float r = color.r * uRR + color.g * uRG + color.b * uRB;
    float g = color.r * uGR + color.g * uGG + color.b * uGB;
    float b = color.r * uBR + color.g * uBG + color.b * uBB;

    fragColor = vec4(r, g, b, texture(uTexture, uv).a);
}
