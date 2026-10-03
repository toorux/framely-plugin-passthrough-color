import colorsys,math,pathlib,struct,zlib
width=96;rows=[]
for y in range(width):
 row=bytearray()
 for x in range(width):
  dx,dy=x-47.5,y-47.5;distance=math.hypot(dx,dy)
  if 19<distance<40:
   rgb=colorsys.hsv_to_rgb((math.atan2(dy,dx)/(2*math.pi))%1,.48,.95);row.extend([round(v*255) for v in rgb]+[255])
  elif distance<=19:row.extend([218,231,239,255])
  else:row.extend([0,0,0,0])
 rows.append(b'\0'+row)
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
pathlib.Path('payload/icon.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,width,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))
