#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uCenterX;
uniform float uCenterY;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(uCenterX, uCenterY);
    vec2 dir = uv - center;

    vec4 color = vec4(0.0);
    int samples = int(clamp(uIntensity * 15.0, 1.0, 30.0));
    float weight = 1.0 / float(samples);

    for (int i = 0; i < 30; i++) {
        if (i >= samples) break;
        float t = (float(i) / float(samples - 1) - 0.5) * 2.0;
        color += texture(uTexture, uv - dir * t * uIntensity * 0.05) * weight;
    }

    fragColor = color;
}
