#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform float uIntensity;    // 0-1, scanline opacity
uniform float uSpacing;      // 1-5, line spacing in pixels
uniform float uFlicker;      // 0-1, brightness flicker amount
uniform float uVignette;     // 0-1, edge darkening


float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    // Scanline pattern
    float lineY = gl_FragCoord.y;
    float scanline = sin(lineY * uSpacing * 10.0) * 0.5 + 0.5;
    scanline = mix(1.0, scanline, uIntensity);

    // Screen flicker
    float flicker = 1.0 - hash(floor(uTime * 24.0)) * uFlicker;

    // Vignette (darkened edges)
    vec2 center = uv - 0.5;
    float vignette = 1.0 - length(center) * uVignette * 1.5;
    vignette = clamp(vignette, 0.0, 1.0);

    // Slight screen warp (CRT bulge)
    float warp = 1.0 + length(center) * 0.05;
    vec2 warpedUV = center * warp + 0.5;
    warpedUV = clamp(warpedUV, 0.0, 1.0);

    vec4 color = texture(uTexture, warpedUV);

    // Apply scanlines, flicker, vignette
    color.rgb *= scanline * flicker * vignette;

    // Subtle green tint (CRT phosphor)
    color.r *= 0.95;
    color.g *= 1.02;
    color.b *= 0.93;

    fragColor = color;
}
