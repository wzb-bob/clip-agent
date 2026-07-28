#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uAngle;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 texel = 1.0 / uResolution * uIntensity * 3.0;
    float angle = uAngle * 3.14159 / 180.0;
    vec2 dir = vec2(cos(angle), sin(angle)) * texel;

    float tl = dot(texture(uTexture, uv - dir).rgb, vec3(0.333));
    float br = dot(texture(uTexture, uv + dir).rgb, vec3(0.333));
    float emboss = (tl - br) * 2.0 + 0.5;

    vec3 color = vec3(emboss);
    float alpha = texture(uTexture, uv).a;
    fragColor = vec4(mix(texture(uTexture, uv).rgb, color, uIntensity), alpha);
}
