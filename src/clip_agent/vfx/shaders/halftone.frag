#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uDotSize;      // 2-20, dot diameter
uniform float uAngle;        // 0-360, screen angle in degrees
uniform float uContrast;     // 0.5-2, contrast boost before threshold


float luminance(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    // Rotate coordinate space for screen angle
    float angleRad = uAngle * 3.14159265 / 180.0;
    float s = sin(angleRad);
    float c = cos(angleRad);
    vec2 rotatedUV = vec2(
        uv.x * c - uv.y * s,
        uv.x * s + uv.y * c
    );

    // Dot grid
    vec2 dotCoord = rotatedUV * uResolution / uDotSize;
    vec2 cellCenter = floor(dotCoord) + 0.5;
    float dist = length(fract(dotCoord) - 0.5) * 2.0;

    // Sample luminance and map to dot size
    float lum = luminance(texture(uTexture, uv).rgb);
    lum = clamp((lum - 0.5) * uContrast + 0.5, 0.0, 1.0);

    float dot = 1.0 - smoothstep(lum - 0.05, lum + 0.05, dist);
    dot = clamp(dot, 0.0, 1.0);

    vec4 baseColor = texture(uTexture, uv);
    fragColor = vec4(baseColor.rgb * dot, baseColor.a);
}
