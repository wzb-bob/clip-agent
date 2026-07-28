#include <flutter/runtime_effect.glsl>

uniform vec2 uResolution;
uniform sampler2D uTexture;
uniform float uShadowR;
uniform float uShadowG;
uniform float uShadowB;
uniform float uMidtoneR;
uniform float uMidtoneG;
uniform float uMidtoneB;
uniform float uHighlightR;
uniform float uHighlightG;
uniform float uHighlightB;
uniform float uPreserveLuminosity;
uniform float uTime;

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    float luminance = dot(color.rgb, vec3(0.2126, 0.7152, 0.0722));

    float shadowMask = 1.0 - smoothstep(0.0, 0.4, luminance);
    float highlightMask = smoothstep(0.6, 1.0, luminance);
    float midtoneMask = 1.0 - shadowMask - highlightMask;

    vec3 shadowAdjust = vec3(uShadowR, uShadowG, uShadowB) / 100.0;
    vec3 midtoneAdjust = vec3(uMidtoneR, uMidtoneG, uMidtoneB) / 100.0;
    vec3 highlightAdjust = vec3(uHighlightR, uHighlightG, uHighlightB) / 100.0;

    vec3 result = color.rgb;
    result += shadowAdjust * shadowMask;
    result += midtoneAdjust * midtoneMask;
    result += highlightAdjust * highlightMask;

    if (uPreserveLuminosity > 0.5) {
        float newLum = dot(result, vec3(0.2126, 0.7152, 0.0722));
        if (newLum > 0.001) {
            result *= luminance / newLum;
        }
    }

    fragColor = vec4(clamp(result, 0.0, 1.0), color.a);
}
