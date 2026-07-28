#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uThreshold;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 texel = 1.0 / uResolution;

    float tl = dot(texture(uTexture, uv + vec2(-1,-1)*texel).rgb, vec3(0.333));
    float t  = dot(texture(uTexture, uv + vec2( 0,-1)*texel).rgb, vec3(0.333));
    float tr = dot(texture(uTexture, uv + vec2( 1,-1)*texel).rgb, vec3(0.333));
    float l  = dot(texture(uTexture, uv + vec2(-1, 0)*texel).rgb, vec3(0.333));
    float r  = dot(texture(uTexture, uv + vec2( 1, 0)*texel).rgb, vec3(0.333));
    float bl = dot(texture(uTexture, uv + vec2(-1, 1)*texel).rgb, vec3(0.333));
    float b  = dot(texture(uTexture, uv + vec2( 0, 1)*texel).rgb, vec3(0.333));
    float br = dot(texture(uTexture, uv + vec2( 1, 1)*texel).rgb, vec3(0.333));

    float gx = -tl - 2.0*l - bl + tr + 2.0*r + br;
    float gy = -tl - 2.0*t - tr + bl + 2.0*b + br;
    float edge = sqrt(gx*gx + gy*gy);

    edge = smoothstep(uThreshold, uThreshold + 0.2, edge);
    vec3 edgeColor = mix(texture(uTexture, uv).rgb, vec3(0.0), edge * uIntensity);
    fragColor = vec4(edgeColor, texture(uTexture, uv).a);
}
