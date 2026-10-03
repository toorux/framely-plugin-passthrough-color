#include <math.h>
#include <stddef.h>
#include <string.h>

/* Pure 528-byte uniform transformation used by the guarded native module.
 * The matching upload implementation copies scratch bytes synchronously.
 * S scales normalized existing tint; it is not standard HSV saturation.
 */
int frame_sv_prepare(void *scratch, const void *original, int monochrome,
                     float saturation, float brightness) {
    static const size_t offsets[] = {304, 464, 480, 496, 512};
    memcpy(scratch, original, 528);
    if (!monochrome) return 0;
    if (!isfinite(saturation)) saturation = 1.0f;
    if (!isfinite(brightness)) brightness = 1.0f;
    saturation = fmaxf(0.0f, fminf(1.0f, saturation));
    brightness = fmaxf(0.25f, fminf(1.5f, brightness));
    if (saturation == 1.0f && brightness == 1.0f) return 0;
    for (size_t k = 0; k < sizeof(offsets)/sizeof(offsets[0]); ++k) {
        float rgb[3];
        memcpy(rgb, (const unsigned char *)original + offsets[k], sizeof(rgb));
        const float y = 0.3f*rgb[0] + 0.5f*rgb[1] + 0.2f*rgb[2];
        for (size_t j = 0; j < 3; ++j)
            rgb[j] = brightness * (y + saturation * (rgb[j] - y));
        memcpy((unsigned char *)scratch + offsets[k], rgb, sizeof(rgb));
    }
    return 1;
}
