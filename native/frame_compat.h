#include <stdint.h>
typedef struct {uintptr_t context,site,upload,vtable;} FrameProfile;
int frame_find_profile(const char*,FrameProfile*);
int frame_sv_probe_file(const char*);
