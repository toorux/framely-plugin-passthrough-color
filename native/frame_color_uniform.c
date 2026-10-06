#include <math.h>
#include <stdint.h>
#include <string.h>
/* A single atomic word gives one coherent color adjustment snapshot. */
uint64_t frame_color_pack(float s,float v,float t){return (uint64_t)lroundf(s*10000)|((uint64_t)lroundf(v*10000)<<16)|((uint64_t)(uint16_t)(int16_t)lroundf(t*10000)<<32);}
void frame_color_unpack(uint64_t p,float* s,float* v,float* t){*s=(p&65535)/10000.f;*v=((p>>16)&65535)/10000.f;*t=(int16_t)(p>>32)/10000.f;}
int frame_color_prepare(void* scratch,const void* original,float s,float v,float t,int shader_ready){
 if(!isfinite(s)||s<0||s>2||!isfinite(v)||v<.25f||v>1.5f||!isfinite(t)||t< -1||t>1)return 0;
 memcpy(scratch,original,528);
 static const size_t offsets[]={304,464,480,496,512};
 /* Positive = warmer; attenuate opposite channels, retaining neutral identity. */
 float gain[]={v*(t<0?1+.35f*t:1),v*(1-.08f*fabsf(t)),v*(t>0?1-.35f*t:1)};
 for(unsigned k=0;k<5;k++){float rgb[3];memcpy(rgb,(const char*)original+offsets[k],12);for(int j=0;j<3;j++)rgb[j]*=gain[j];memcpy((char*)scratch+offsets[k],rgb,12);}
 if(shader_ready){memcpy((char*)scratch+476,&s,4);}
 return 1;
}
