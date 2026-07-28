#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uEchoTime;     // 0.01-0.5 seconds
uniform float uEchoCount;    // 1-10
uniform float uDecay;        // 0-1 opacity falloff
uniform float uIntensity;    // 0-1 overall blend


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 base = texture(uTexture, uv);
    vec4 echo = vec4(0.0);

    int count = int(clamp(uEchoCount, 1.0, 10.0));
    for (int i = 1; i <= 10; i++) {
        if (i > count) break;
        float t = float(i) * uEchoTime * 0.1;
        float alpha = pow(uDecay, float(i));
        vec2 offsetUV = uv - vec2(t, 0.0); // horizontal echo
        offsetUV = clamp(offsetUV, 0.0, 1.0);
        echo += texture(uTexture, offsetUV) * alpha;
    }

    fragColor = mix(base, (base + echo) / (1.0 + uDecay), uIntensity);
}
