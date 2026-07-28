#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;      // incoming clip
uniform sampler2D uPrevTexture;  // outgoing clip
uniform vec2 uResolution;
uniform float uProgress;         // 0-1
uniform float uZoomAmount;       // max zoom scale (1.5 = 150%)
uniform float uFeather;          // edge softness
uniform vec2 uCenter;            // zoom center 0-1 (default 0.5, 0.5)


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = uCenter;

    // Ease progress
    float p = smoothstep(0.0, 1.0, uProgress);

    // Zoom direction: first half zooms out old, second half zooms in new
    float zoomOld = 1.0 + (1.0 - p) * uZoomAmount;
    float zoomNew = 1.0 + p * uZoomAmount;

    // Radial UVs relative to center
    vec2 oldUV = (uv - center) / zoomOld + center;
    vec2 newUV = (uv - center) / zoomNew + center;

    // Clamp UVs to edge (extend mode)
    oldUV = clamp(oldUV, 0.0, 1.0);
    newUV = clamp(newUV, 0.0, 1.0);

    vec4 outgoing = texture(uPrevTexture, oldUV);
    vec4 incoming = texture(uTexture, newUV);

    // Radial distance for feather
    float dist = length(uv - center) * 1.5;
    float transition = smoothstep(p - uFeather, p + uFeather, dist);

    // Motion blur on incoming: slight radial blur
    float blurAmount = uZoomAmount * p * 0.02;
    vec4 blurred = vec4(0.0);
    int samples = 8;
    for (int i = 0; i < 8; i++) {
        float t = (float(i) / float(samples - 1) - 0.5) * blurAmount;
        vec2 buv = (uv - center) * (1.0 + t) + center;
        blurred += texture(uTexture, clamp(buv, 0.0, 1.0));
    }
    blurred /= float(samples);

    vec4 blended = mix(outgoing, blurred, transition);

    // Light flash at midpoint
    float flash = exp(-abs(p - 0.5) * 20.0) * 0.3;
    blended.rgb += flash * vec3(1.0, 0.95, 0.9);

    fragColor = blended;
}
