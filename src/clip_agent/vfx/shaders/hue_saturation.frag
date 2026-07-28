#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uHue;         // -180 to 180 degrees
uniform float uSaturation;  // -100 to 100
uniform float uLightness;   // -100 to 100


vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = c.g < c.b ? vec4(c.bg, K.wz) : vec4(c.gb, K.xy);
    vec4 q = c.r < p.x ? vec4(p.xyw, c.r) : vec4(c.r, p.yzx);
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    vec3 hsv = rgb2hsv(color.rgb);

    hsv.x = fract(hsv.x + uHue / 360.0);
    hsv.y = clamp(hsv.y + uSaturation / 100.0, 0.0, 1.0);
    hsv.z = clamp(hsv.z + uLightness / 100.0, 0.0, 1.0);

    vec3 rgb = hsv2rgb(hsv);
    fragColor = vec4(rgb, color.a);
}
