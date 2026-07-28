#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;       // 0-1 overall strength
uniform float uTime;            // seconds, drives animation
uniform float uBlockSize;       // glitch block size 4-64 px
uniform float uColorSplit;      // 0-1 RGB channel separation
uniform float uScanlineJitter;  // 0-1 horizontal scanline displacement
uniform float uSeed;            // random seed


float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float hash3D(vec3 p) {
    return hash(vec2(hash(p.xy), p.z));
}

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;

    // Block-based glitch
    float blockY = floor(uv.y * uResolution.y / max(uBlockSize, 1.0));
    float blockX = floor(uv.x * uResolution.x / max(uBlockSize, 1.0));
    float blockHash = hash(vec2(blockX, blockY) + floor(uTime * 30.0) + uSeed);

    // Randomly displace blocks
    float displaceChance = uIntensity * 0.3;
    float shouldDisplace = step(displaceChance, blockHash);

    // Displacement amount
    float dispX = (hash(vec2(blockY, uTime + uSeed)) - 0.5) * uIntensity * 0.15;
    float dispY = (hash(vec2(blockY + 100.0, uTime)) - 0.5) * uIntensity * 0.05;
    vec2 dispUV = uv + vec2(dispX, dispY) * shouldDisplace;

    // Scanline jitter
    float scanline = sin(uv.y * uResolution.y * 0.1 + uTime * 10.0) * uScanlineJitter * uIntensity * 0.01;
    dispUV.x += scanline * hash(vec2(floor(uv.y * 20.0), uTime));

    // Clamp UV
    dispUV = clamp(dispUV, 0.0, 1.0);

    // RGB channel split
    float splitAmount = uColorSplit * uIntensity * 0.03;
    vec2 splitDir = vec2(1.0, 0.0); // horizontal split

    float r = texture(uTexture, dispUV + splitDir * splitAmount).r;
    float g = texture(uTexture, dispUV).g;
    float b = texture(uTexture, dispUV - splitDir * splitAmount).b;
    float a = texture(uTexture, dispUV).a;

    vec3 color = vec3(r, g, b);

    // Random color channel corruption
    float corruptChance = uIntensity * 0.15;
    float channelHash = hash(vec2(blockX, blockY) + floor(uTime * 10.0) + uSeed + 500.0);
    if (channelHash < corruptChance) {
        int channel = int(hash(vec2(blockY + 200.0, uTime)) * 3.0);
        if (channel == 0) color.r = hash(vec2(blockX, uTime));
        if (channel == 1) color.g = hash(vec2(blockY, uTime));
        if (channel == 2) color.b = hash(vec2(blockX + blockY, uTime));
    }

    // Horizontal band corruption (full row glitch)
    float bandHash = hash(vec2(blockY, floor(uTime * 5.0) + uSeed + 1000.0));
    float bandChance = uIntensity * 0.08;
    if (bandHash < bandChance) {
        float shift = (hash(vec2(blockY, uTime)) - 0.5) * uIntensity * 0.5;
        color = texture(uTexture, clamp(vec2(uv.x + shift, uv.y), 0.0, 1.0)).rgb;
    }

    // Color quantization / bit crush in glitch blocks
    float bitChance = uIntensity * 0.1;
    if (hash(vec2(blockX, blockY) + uSeed + 800.0) < bitChance) {
        float bits = mix(256.0, 4.0, uIntensity);
        color = floor(color * bits) / bits;
    }

    // Subtle VHS-style bottom distortion bar
    float barDist = abs(uv.y - 0.9);
    float barHeight = 0.03 * uIntensity;
    if (barDist < barHeight) {
        float barShift = (hash(vec2(uv.y * 200.0, uTime)) - 0.5) * uIntensity * 0.1;
        color = texture(uTexture, clamp(vec2(uv.x + barShift, uv.y), 0.0, 1.0)).rgb;
    }

    fragColor = vec4(color, a);
}
