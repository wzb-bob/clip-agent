#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform float uScale;        // 1-50, noise zoom
uniform float uOctaves;      // 1-6, fractal detail layers
uniform float uIntensity;    // 0-1, blend amount
uniform float uMonochrome;    // true=luminance noise, false=color noise


float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noiseValue(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);

    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));

    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    float maxValue = 0.0;

    for (int i = 0; i < 6; i++) {
        if (i >= int(uOctaves)) break;
        value += amplitude * noiseValue(p * frequency);
        maxValue += amplitude;
        frequency *= 2.0;
        amplitude *= 0.5;
    }

    return value / maxValue;
}

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 base = texture(uTexture, uv);

    vec2 noiseCoord = uv * uScale + uTime * 0.5;
    float n = fbm(noiseCoord);

    if (uMonochrome > 0.5) {
        base.rgb = mix(base.rgb, vec3(n), uIntensity);
    } else {
        float nr = fbm(noiseCoord + vec2(0.0, 0.0));
        float ng = fbm(noiseCoord + vec2(1.7, 9.2));
        float nb = fbm(noiseCoord + vec2(8.3, 2.8));
        base.rgb = mix(base.rgb, vec3(nr, ng, nb), uIntensity);
    }

    fragColor = base;
}
