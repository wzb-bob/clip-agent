#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uDistortion;   // -1 to 1, negative=barrel, positive=pincushion
uniform float uZoom;         // 0.5-2, scale compensation


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = uv - 0.5;

    float r = length(center);
    float r2 = r * r;

    // Distortion formula: r' = r * (1 + k * r^2)
    float distortion = 1.0 + uDistortion * r2;
    vec2 distortedUV = center * distortion / uZoom + 0.5;

    if (distortedUV.x < 0.0 || distortedUV.x > 1.0 ||
        distortedUV.y < 0.0 || distortedUV.y > 1.0) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    fragColor = texture(uTexture, distortedUV);
}
