#include <flutter/runtime_effect.glsl>


uniform sampler2D uTexture;
uniform vec2 uResolution;
uniform float uMaxDisplacement;  // max time offset in seconds
uniform float uTimeResolution;   // frames per second
uniform float uScale;            // displacement scale multiplier
uniform float uStretch;          // stretch displacement map


float luminance(vec3 c) {
    return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

out vec4 fragColor;

void main() {
    vec2 uv = FlutterFragCoord().xy / uResolution;
    vec4 color = texture(uTexture, uv);

    // Use current pixel luminance as displacement amount
    float lum = luminance(color.rgb);

    // Displace UV along gradient of luminance
    // Brighter = sample later, darker = sample earlier
    vec2 grad;
    grad.x = luminance(texture(uTexture, uv + vec2(1.0 / uResolution.x, 0.0)).rgb)
           - luminance(texture(uTexture, uv - vec2(1.0 / uResolution.x, 0.0)).rgb);
    grad.y = luminance(texture(uTexture, uv + vec2(0.0, 1.0 / uResolution.y)).rgb)
           - luminance(texture(uTexture, uv - vec2(0.0, 1.0 / uResolution.y)).rgb);

    // Displace along gradient direction, scaled by luminance
    float displacement = (lum - 0.5) * uMaxDisplacement * uScale;
    vec2 offsetUV = uv + grad * displacement * uStretch;

    // Clamp and sample at displaced position
    offsetUV = clamp(offsetUV, 0.0, 1.0);
    vec4 displaced = texture(uTexture, offsetUV);

    // Fade out extreme displacements to avoid artifacts
    float fade = 1.0 - abs(lum - 0.5) * 2.0;
    fade = smoothstep(0.0, 0.3, fade);

    fragColor = mix(color, displaced, fade * 0.5);
}
