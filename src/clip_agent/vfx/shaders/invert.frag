#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);
    vec3 inverted = 1.0 - color.rgb;
    fragColor = vec4(mix(color.rgb, inverted, uIntensity), color.a);
}
