"""Render firmware C++ drawing functions verbatim as browser animation atlases."""
from pathlib import Path
import subprocess
import tempfile
from PIL import Image

root = Path(__file__).resolve().parent
source_path = root.parent / 'PoetryCameraDirector/DetectiveDisplay.cpp'
if not source_path.exists():
    source_path = root.parent / 'firmware/PoetryCameraDirector/DetectiveDisplay.cpp'
source = source_path.read_text()
drawing = source[source.index('uint16_t swap16'):source.index('bool ioxWrite')]
oval = source[source.index('void oval'):source.index('uint16_t swap16')]
prefix = r'''
#include <cstdint>
#include <cmath>
#include <cstring>
#include <cctype>
#include <algorithm>
#include <cstdio>
using std::min; using std::max;
constexpr int W=284,H=240;
constexpr uint16_t PAPER=0xDF13,INK=0x0841,RED=0xF28D,GOLD=0x9F27,MUTED=0x55B7,BLACK=0,WHITE=0xF7DC;
constexpr uint16_t SPACE=0x1127,SKIN=0xD6B6,HAIR=0x7E5C;
enum class DetectiveScreenState {Boot,Setup,Ready,Capturing,Deducing,Printing,Error};
DetectiveScreenState currentState=DetectiveScreenState::Deducing;
bool ready=true,connected=true;uint8_t faceVariant=1;
uint16_t pixels[W*H];uint16_t *canvas=pixels;
uint32_t tick=850;uint32_t millis(){return tick;}
void rect(int,int,int,int,uint16_t);
bool present(){return true;}
'''
suffix = r'''
int main(){
  for(auto state:{DetectiveScreenState::Ready,DetectiveScreenState::Capturing,DetectiveScreenState::Deducing,DetectiveScreenState::Printing}){
    currentState=state;
    for(int talking=0;talking<2;talking++)for(int i=0;i<36;i++){
      tick=i*120;faceVariant=tick/3400;render(talking);
      fwrite(pixels,2,W*H,stdout);
    }
  }
}
'''
with tempfile.TemporaryDirectory() as directory:
    binary = str(Path(directory) / 'screen-render')
    subprocess.run(['clang++','-std=c++17','-x','c++','-','-o',binary], input=(prefix+oval+drawing+suffix).encode(),check=True)
    raw = subprocess.check_output([binary])
out = root / 'screen-frames'; out.mkdir(exist_ok=True)
index = 0
for state in ['ready', 'capturing', 'deducing', 'printing']:
    for talking in ['silent', 'talking']:
        atlas = Image.new('RGB',(284*8,240*5))
        for frame in range(36):
            data = raw[index*240*284*2:(index+1)*240*284*2]; index += 1
            rgb = bytearray()
            for pos in range(0,len(data),2):
                c = int.from_bytes(data[pos:pos+2],'big')
                rgb.extend((((c>>11)&31)*255//31,((c>>5)&63)*255//63,(c&31)*255//31))
            atlas.paste(Image.frombytes('RGB',(284,240),bytes(rgb)),((frame%8)*284,(frame//8)*240))
        atlas.save(out / f'{state}-{talking}.png')
print('Rendered 288 frames directly from firmware')
