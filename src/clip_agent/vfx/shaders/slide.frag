#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;      // incoming clip
uniform sampler2D uPrevTexture;  // outgoing clip
uniform vec2 uResolution;
uniform float uProgress;         // 0-1
uniform vec2 uDirection;         // normalized slide direction (e.g. 1,0 = right)
uniform float uFeather;          // edge feather 0-0.2
uniform float uBounce;           // bounce intensity 0-1


float easeOutBounce(float t) {
    float n1 = 7.5625;
    float d1 = 2.75;
    if (t < 1.0 / d1) {
        return n1 * t * t;
    } else if (t < 2.0 / d1) {
        t -= 1.5 / d1;
        return n1 * t * t + 0.75;
    } else if (t < 2.5 / d1) {
        t -= 2.25 / d1;
        return n1 * t * t + 0.9375;
    } else {
        t -= 2.625 / d1;
        return n1 * t * t + 0.984375;
    }
}

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 dir = normalize(uDirection);

    // Apply easing
    float p = uProgress;
    if (uBounce > 0.01) {
        p = mix(p, easeOutBounce(p), uBounce);
    }

    // Compute distance along slide direction
    float dist = dot(uv - 0.5, dir);

    // Threshold for transition
    float threshold = (p - 0.5) * 2.0; // map 0-1 to -1 to 1
    float mask = smoothstep(threshold - uFeather, threshold + uFeather, dist);

    vec4 incoming = texture(uTexture, uv);
    vec4 outgoing = texture(uPrevTexture, uv);

    fragColor = mix(outgoing, incoming, mask);
}
