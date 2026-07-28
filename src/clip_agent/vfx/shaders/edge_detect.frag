#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uThreshold;    // 0-1, edge sensitivity
uniform float uIntensity;    // 0-2, edge brightness
uniform float uInvert;        // white edges on black vs black edges on white


float luminance(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 texel = 1.0 / uResolution;

    // Sample 3x3 neighborhood
    float tl = luminance(texture(uTexture, uv + vec2(-1, -1) * texel).rgb);
    float t  = luminance(texture(uTexture, uv + vec2( 0, -1) * texel).rgb);
    float tr = luminance(texture(uTexture, uv + vec2( 1, -1) * texel).rgb);
    float l  = luminance(texture(uTexture, uv + vec2(-1,  0) * texel).rgb);
    float r  = luminance(texture(uTexture, uv + vec2( 1,  0) * texel).rgb);
    float bl = luminance(texture(uTexture, uv + vec2(-1,  1) * texel).rgb);
    float b  = luminance(texture(uTexture, uv + vec2( 0,  1) * texel).rgb);
    float br = luminance(texture(uTexture, uv + vec2( 1,  1) * texel).rgb);

    // Sobel operators
    float gx = -tl - 2.0*l - bl + tr + 2.0*r + br;
    float gy = -tl - 2.0*t - tr + bl + 2.0*b + br;

    float edge = sqrt(gx * gx + gy * gy);
    edge = smoothstep(uThreshold, uThreshold + 0.1, edge) * uIntensity;

    if (uInvert > 0.5) {
        edge = 1.0 - edge;
    }

    vec4 baseColor = texture(uTexture, uv);
    fragColor = vec4(vec3(edge), baseColor.a);
}
