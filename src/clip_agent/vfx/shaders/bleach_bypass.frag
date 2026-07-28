#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec3 color = texture(uTexture, uv).rgb;
    float luminance = dot(color, vec3(0.299, 0.587, 0.114));
    vec3 desaturated = mix(color, vec3(luminance), 0.8);
    float contrast = smoothstep(0.2, 0.8, luminance);
    vec3 bleach = mix(desaturated, desaturated * (1.5 - contrast * 0.5), uIntensity);
    fragColor = vec4(bleach, texture(uTexture, uv).a);
}
