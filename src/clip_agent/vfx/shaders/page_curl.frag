#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;      // incoming clip (underneath)
uniform sampler2D uPrevTexture;  // outgoing clip (page being curled)
uniform vec2 uResolution;
uniform float uProgress;         // 0-1
uniform float uAngle;            // curl direction angle 0-360
uniform float uCurlRadius;       // radius of curl cylinder
uniform float uShadowIntensity;  // 0-1 shadow darkness


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    // Curl direction
    float angleRad = uAngle * 3.14159265 / 180.0;
    vec2 dir = vec2(cos(angleRad), sin(angleRad));

    // Project UV onto curl direction
    float proj = dot(uv, dir);

    // Curl threshold: progress controls how far the curl has advanced
    float threshold = 1.0 - uProgress * 1.4;

    // Shadow gradient near the curl line
    float curlLine = proj - threshold;
    float shadowWidth = 0.08;
    float shadow = 1.0 - smoothstep(0.0, shadowWidth, abs(curlLine)) * uShadowIntensity;

    // Backside of the page: reflect UV
    float backReflect = threshold - curlLine;
    vec2 backUV = uv - 2.0 * backReflect * dir;

    vec4 outgoing;
    if (proj < threshold) {
        // Before curl: show outgoing clip
        outgoing = texture(uPrevTexture, uv);
    } else {
        // After curl: show back of page (flipped) or incoming clip
        float backFactor = smoothstep(threshold, threshold + uCurlRadius, proj);
        vec4 backPage = texture(uPrevTexture, clamp(backUV, 0.0, 1.0));
        backPage.rgb *= 0.6; // darker back side
        vec4 incoming = texture(uTexture, uv);
        outgoing = mix(backPage, incoming, backFactor);
    }

    // Apply shadow
    outgoing.rgb *= shadow;

    // Highlight on curl edge
    float highlight = exp(-abs(curlLine) * 30.0) * 0.4;
    outgoing.rgb += highlight * vec3(1.0, 0.95, 0.85);

    fragColor = outgoing;
}
