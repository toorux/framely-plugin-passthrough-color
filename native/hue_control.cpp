#include "openvr.h"
#include "hue_value.h"
#include <cstdio>
#include <cstring>
int main(int argc,char** argv){
 bool get=argc==2&&!std::strcmp(argv[1],"--get");bool set=argc==3&&!std::strcmp(argv[1],"--set");bool validate=argc==3&&!std::strcmp(argv[1],"--validate");float value=0;
 if(!(get||set||validate)||((set||validate)&&!parse_hue(argv[2],value))){std::fprintf(stderr,"Expected --get | --set <finite 0..1> | --validate <value>\n");return 1;}
 if(validate){std::printf("{\"hue\":%.9g}\n",value);return 0;}
 vr::EVRInitError init{};vr::VR_Init(&init,vr::VRApplication_Background);
 if(init){std::fprintf(stderr,"SteamVR settings connection failed (%d)\n",int(init));return 2;}
 auto* settings=static_cast<vr::IVRSettings*>(vr::VR_GetGenericInterface(vr::IVRSettings_Version,&init));if(!settings||init){vr::VR_Shutdown();return 3;}
 vr::EVRSettingsError error{};float hue=settings->GetFloat("camera","monochromeTintHue",&error);
 if(!error&&set){settings->SetFloat("camera","monochromeTintHue",value,&error);if(!error)hue=settings->GetFloat("camera","monochromeTintHue",&error);}
 if(error){std::fprintf(stderr,"SteamVR settings: %s\n",settings->GetSettingsErrorNameFromEnum(error));vr::VR_Shutdown();return 4;}
 if(!std::isfinite(hue)||hue<0||hue>1){vr::VR_Shutdown();return 5;}
 std::printf("{\"hue\":%.9g}\n",hue);vr::VR_Shutdown();return 0;
}
