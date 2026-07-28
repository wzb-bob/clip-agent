#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uTime;
uniform float uSpeed;        // 1-20, pulses per second
uniform float uIntensity;    // 0-1, flash strength
uniform vec3 uFlashColor;    // flash color (white default)


out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    float pulse = sin(uTime * uSpeed * 3.14159265 * 2.0) * 0.5 + 0.5;
    pulse = pow(pulse, 3.0); // sharpen the pulse

    // Screen blend flash
    vec3 result = color.rgb + uFlashColor * pulse * uIntensity;
    result = clamp(result, 0.0, 1.0);

    fragColor = vec4(result, color.a);
}
