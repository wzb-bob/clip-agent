#include <flutter/runtime_effect.glsl>

uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uIntensity;
uniform float uAngle;


uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(0.5);
    vec2 dir = uv - center;
    float dist = length(dir);
    float angle = atan(dir.y, dir.x);

    float rays = abs(sin(angle * 16.0 + uAngle * 3.14159 / 180.0));
    rays = pow(rays, 3.0);
    float fade = 1.0 - smoothstep(0.0, 1.0, dist * 2.0);
    float glow = rays * fade * uIntensity;

    vec3 color = texture(uTexture, uv).rgb;
    color += vec3(1.0, 0.95, 0.8) * glow * 0.4;
    fragColor = vec4(color, 1.0);
}
