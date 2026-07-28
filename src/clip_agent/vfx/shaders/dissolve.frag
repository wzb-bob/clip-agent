#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uProgress;    // 0-1
uniform float uFeather;     // 0-0.5


float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    float noise = hash(floor(uv * 500.0));
    float alpha = smoothstep(uProgress - uFeather, uProgress + uFeather, noise);

    fragColor = texture(uTexture, uv) * alpha;
}
