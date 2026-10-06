#include "openvr.h"
#include "hue_value.h"
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <dlfcn.h>
#include <algorithm>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <filesystem>
#include <fstream>
#include <link.h>
#include "frame_shapes.h"
struct CodeRange {uintptr_t base,address;size_t size;bool found;};
static int executable_range(dl_phdr_info* info,size_t,void* opaque){auto& q=*static_cast<CodeRange*>(opaque);if(info->dlpi_addr!=q.base)return 0;for(int i=0;i<info->dlpi_phnum;i++){auto& p=info->dlpi_phdr[i];uintptr_t start=info->dlpi_addr+p.p_vaddr;if(p.p_type==PT_LOAD&&(p.p_flags&PF_X)&&q.address>=start&&q.address-start<=p.p_memsz&&q.size<=p.p_memsz-(q.address-start)){q.found=true;return 1;}}return 0;}
static bool rgb_available(){
 std::error_code error;auto nodes=std::filesystem::directory_iterator("/sys/class/video4linux",error);if(error)return false;
 for(const auto& node:nodes){
  std::ifstream f(node.path()/"name");std::string name;std::getline(f,name);
  if(name.rfind("arcimx616 ",0)!=0)continue;
  int fd=open(("/dev/"+node.path().filename().string()).c_str(),O_RDONLY|O_NONBLOCK|O_CLOEXEC);
  if(fd<0)continue;
  uint32_t connected=0;int r=ioctl(fd,0x800456c1UL,&connected);close(fd);
  if(!r&&connected==1)return true;
 }return false;
}
static int mode(const char* requested){
 vr::EVRInitError e{};void* instance=vr::VR_GetGenericInterface("IVRCameraPassthroughInternal_001",&e);
 if(!instance||e){std::fprintf(stderr,"相机模式接口不可用\n");return 6;}
 auto** methods=*reinterpret_cast<void***>(instance);
 // Validate method bodies and their five-byte layout, independent of load offsets.
 const uint32_t* shapes[]={visible_shape,show_shape,get_shape,set_shape};
 const size_t sizes[]={sizeof(visible_shape),sizeof(show_shape),sizeof(get_shape),sizeof(set_shape)};
 uintptr_t owner=0;
 for(int j=0;j<4;j++){
  Dl_info d{};if(!dladdr(methods[j+7],&d)){std::fprintf(stderr,"相机模式方法不可用\n");return 6;}
  if(!j)owner=(uintptr_t)d.dli_fbase;
  CodeRange q{owner,(uintptr_t)methods[j+7],sizes[j],false};dl_iterate_phdr(executable_range,&q);
  if((uintptr_t)d.dli_fbase!=owner||!q.found||!frame_shape(methods[j+7],shapes[j],sizes[j]/4)){std::fprintf(stderr,"相机模式接口结构不兼容；不影响独立调色功能\n");return 6;}
 }
 using Visible=int(*)(void*,bool*);using Show=void(*)(void*,bool);
 using Get=bool(*)(void*,uint8_t*);using Set=void(*)(void*,const uint8_t*);
 auto get=reinterpret_cast<Get>(methods[9]);auto read=reinterpret_cast<Visible>(methods[7]);
 uint8_t config[5]={255,255,255,255,255};get(instance,config);
 if(!std::all_of(config,config+5,[](uint8_t v){return v<=1;})){std::fprintf(stderr,"相机模式配置无效\n");return 6;}
 bool visible=false;bool available=rgb_available();if(read(instance,&visible)!=0)return 6;
 uint8_t original[5];std::memcpy(original,config,5);bool original_visible=visible;
 auto rollback=[&](){reinterpret_cast<Set>(methods[10])(instance,original);reinterpret_cast<Show>(methods[8])(instance,original_visible);};
 if(requested){
  if(!std::strcmp(requested,"color")&&!available){std::fprintf(stderr,"未检测到可用彩色透视相机\n");return 7;}
  if(std::strcmp(requested,"off")){
   if(!config[0]){std::fprintf(stderr,"系统相机尚未就绪\n");return 7;}
   config[2]=!std::strcmp(requested,"color");reinterpret_cast<Set>(methods[10])(instance,config);
   uint8_t confirmed[5];get(instance,confirmed);if(std::memcmp(config,confirmed,5)){rollback();std::fprintf(stderr,"相机来源切换被系统拒绝\n");return 7;}
  }
  reinterpret_cast<Show>(methods[8])(instance,std::strcmp(requested,"off")!=0);
  if(read(instance,&visible)!=0||visible!=(std::strcmp(requested,"off")!=0)){rollback();std::fprintf(stderr,"透视开关回读失败\n");return 7;}
 }
 const char* value=!visible?"off":config[2]&&available?"color":"mono";
 std::printf("{\"mode\":\"%s\",\"colorAvailable\":%s}\n",value,available?"true":"false");return 0;
}
int main(int argc,char** argv){
 bool mode_get=argc==2&&!std::strcmp(argv[1],"--mode-get");bool mode_set=argc==3&&!std::strcmp(argv[1],"--mode-set")&&(!std::strcmp(argv[2],"off")||!std::strcmp(argv[2],"color")||!std::strcmp(argv[2],"mono"));
 bool get=argc==2&&!std::strcmp(argv[1],"--get");bool set=argc==3&&!std::strcmp(argv[1],"--set");bool validate=argc==3&&!std::strcmp(argv[1],"--validate");float value=0;
 if(!(get||set||validate||mode_get||mode_set)||((set||validate)&&!parse_hue(argv[2],value))){std::fprintf(stderr,"Expected --get | --set <finite 0..1> | --validate <value>\n");return 1;}
 if(validate){std::printf("{\"hue\":%.9g}\n",value);return 0;}
 vr::EVRInitError init{};vr::VR_Init(&init,vr::VRApplication_Background);
 if(init){std::fprintf(stderr,"SteamVR settings connection failed (%d)\n",int(init));return 2;}
 if(mode_get||mode_set){int result=mode(mode_set?argv[2]:nullptr);vr::VR_Shutdown();return result;}
 auto* settings=static_cast<vr::IVRSettings*>(vr::VR_GetGenericInterface(vr::IVRSettings_Version,&init));if(!settings||init){vr::VR_Shutdown();return 3;}
 vr::EVRSettingsError error{};float hue=settings->GetFloat("camera","monochromeTintHue",&error);
 if(!error&&set){settings->SetFloat("camera","monochromeTintHue",value,&error);if(!error)hue=settings->GetFloat("camera","monochromeTintHue",&error);}
 if(error){std::fprintf(stderr,"SteamVR settings: %s\n",settings->GetSettingsErrorNameFromEnum(error));vr::VR_Shutdown();return 4;}
 if(!std::isfinite(hue)||hue<0||hue>1){vr::VR_Shutdown();return 5;}
 std::printf("{\"hue\":%.9g}\n",hue);vr::VR_Shutdown();return 0;
}
