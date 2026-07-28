#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uStripeCount;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    float stripes = sin(uv.y * uStripeCount * 3.14159 * 2.0);
    float mask = smoothstep(0.0, 0.3 * (1.0 - uIntensity), abs(stripes));
    float offset = stripes * 0.02 * uIntensity;
    vec2 uv2 = uv + vec2(offset, 0.0);
    fragColor = texture(uTexture, uv2) * vec4(vec3(mask), 1.0);
}
