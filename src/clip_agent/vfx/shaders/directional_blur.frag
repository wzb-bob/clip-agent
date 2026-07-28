#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uAngle;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    float angle = uAngle * 3.14159 / 180.0;
    vec2 dir = vec2(cos(angle), sin(angle)) * uIntensity / uResolution;

    vec4 color = vec4(0.0);
    int samples = int(clamp(uIntensity * 10.0, 1.0, 40.0));
    float weight = 1.0 / float(samples);

    for (int i = 0; i < 40; i++) {
        if (i >= samples) break;
        float t = (float(i) / float(samples - 1) - 0.5) * 2.0;
        color += texture(uTexture, uv + dir * t * float(samples)) * weight;
    }

    fragColor = color;
}
