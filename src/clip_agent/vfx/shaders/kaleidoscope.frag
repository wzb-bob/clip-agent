#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uSegments;     // 2-32, number of mirror segments
uniform float uRotation;     // 0-360, rotation offset
uniform float uCenterX;      // 0-1
uniform float uCenterY;      // 0-1


const float PI = 3.14159265359;

uniform float uTime;
out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec2 center = vec2(uCenterX, uCenterY);

    vec2 delta = uv - center;
    float angle = atan(delta.y, delta.x) + uRotation * PI / 180.0;
    float radius = length(delta);

    float segmentAngle = 2.0 * PI / uSegments;
    float mirroredAngle = mod(angle, segmentAngle * 2.0);

    if (mirroredAngle > segmentAngle) {
        mirroredAngle = segmentAngle * 2.0 - mirroredAngle;
    }

    vec2 sampleUV = center + vec2(cos(mirroredAngle - uRotation * PI / 180.0),
                                   sin(mirroredAngle - uRotation * PI / 180.0)) * radius;
    sampleUV = clamp(sampleUV, 0.0, 1.0);

    fragColor = texture(uTexture, sampleUV);
}
