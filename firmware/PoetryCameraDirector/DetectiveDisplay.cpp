#include "DetectiveDisplay.h"

#include <Wire.h>
#include <math.h>
#include "img_converters.h"
#include "driver/spi_master.h"
#include "esp_heap_caps.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_st7789.h"

namespace {
constexpr int W = 284, H = 240;
constexpr int PIN_MOSI = 1, PIN_CLK = 5, PIN_DC = 3, PIN_CS = 6;
constexpr uint8_t IOX = 0x24;
constexpr uint16_t PAPER = 0xDF13, INK = 0x0841, RED = 0xF28D;
constexpr uint16_t GOLD = 0x9F27, MUTED = 0x55B7, BLACK = 0x0000, WHITE = 0xF7DC;
constexpr uint16_t SPACE = 0x1127, SKIN = 0xD6B6, HAIR = 0x7E5C;

esp_lcd_panel_handle_t panel = nullptr;
esp_lcd_panel_io_handle_t panelIo = nullptr;
uint16_t *canvas = nullptr;
uint16_t *dmaStrip = nullptr;
volatile DetectiveScreenState currentState = DetectiveScreenState::Boot;
bool connected = false, ready = false, talkingShown = false;
uint8_t faceVariant = 0;
uint32_t lastFaceChange = 0;
String currentDetail;
SemaphoreHandle_t frameDone = nullptr;
TaskHandle_t displayOwner = nullptr;
volatile bool selfTestRequested = false;
uint32_t lastFrame = 0;
uint8_t *decoded = nullptr;
size_t decodedCapacity = 0;
void rect(int x, int y, int w, int h, uint16_t c);
bool onFrameDone(esp_lcd_panel_io_handle_t, esp_lcd_panel_io_event_data_t *, void *) {
  BaseType_t wake = pdFALSE;
  xSemaphoreGiveFromISR(frameDone, &wake);
  return wake == pdTRUE;
}
bool present() {
  // A full PSRAM frame needs an internal DMA bounce buffer larger than the
  // free heap after audio starts. Reuse a bounded 16-row internal DMA strip.
  for(int y=0;y<H;y+=16){
    int rows=min(16,H-y);
    memcpy(dmaStrip,canvas+y*W,W*rows*2);
    if(esp_lcd_panel_draw_bitmap(panel,0,y,W,y+rows,dmaStrip)!=ESP_OK)return false;
    xSemaphoreTake(frameDone,portMAX_DELAY);
  }
  return true;
}
void oval(int cx,int cy,int rx,int ry,uint16_t color){
  for(int y=-ry;y<=ry;y++){
    int dx=(int)(rx*sqrtf(max(0.0f,1.0f-(float)(y*y)/(ry*ry))));
    rect(cx-dx,cy+y,2*dx+1,1,color);
  }
}

uint16_t swap16(uint16_t c) { return (c << 8) | (c >> 8); }
void px(int x, int y, uint16_t c) { if ((unsigned)x < W && (unsigned)y < H) canvas[y * W + x] = swap16(c); }
void fill(uint16_t c) { uint16_t s = swap16(c); for (int i = 0; i < W * H; ++i) canvas[i] = s; }
void rect(int x, int y, int w, int h, uint16_t c) {
  for (int yy = max(0, y); yy < min(H, y + h); ++yy)
    for (int xx = max(0, x); xx < min(W, x + w); ++xx) px(xx, yy, c);
}
void frame(int x, int y, int w, int h, int t, uint16_t c) {
  rect(x, y, w, t, c); rect(x, y + h - t, w, t, c); rect(x, y, t, h, c); rect(x + w - t, y, t, h, c);
}
void line(int x0, int y0, int x1, int y1, uint16_t c, int thick = 1) {
  int dx = abs(x1-x0), sx = x0<x1?1:-1, dy = -abs(y1-y0), sy = y0<y1?1:-1, e=dx+dy;
  while (true) { rect(x0-thick/2,y0-thick/2,thick,thick,c); if(x0==x1&&y0==y1) break; int e2=2*e; if(e2>=dy){e+=dy;x0+=sx;} if(e2<=dx){e+=dx;y0+=sy;} }
}
void circle(int cx, int cy, int r, uint16_t c, bool solid=false) {
  for (int y=-r; y<=r; ++y) for (int x=-r; x<=r; ++x) {
    int d=x*x+y*y; if (solid ? d<=r*r : (d<=r*r && d>=(r-2)*(r-2))) px(cx+x,cy+y,c);
  }
}

// Compact 5x7 capitals used by the appliance UI.
const uint8_t* glyph(char c) {
  static const uint8_t blank[5]={0,0,0,0,0};
  static const uint8_t nums[10][5]={{62,81,73,69,62},{0,66,127,64,0},{66,97,81,73,70},{33,65,69,75,49},{24,20,18,127,16},{39,69,69,69,57},{60,74,73,73,48},{1,113,9,5,3},{54,73,73,73,54},{6,73,73,41,30}};
  static const uint8_t az[26][5]={
    {126,17,17,17,126},{127,73,73,73,54},{62,65,65,65,34},{127,65,65,34,28},{127,73,73,73,65},{127,9,9,9,1},{62,65,73,73,122},{127,8,8,8,127},{0,65,127,65,0},{32,64,65,63,1},{127,8,20,34,65},{127,64,64,64,64},{127,2,12,2,127},{127,4,8,16,127},{62,65,65,65,62},{127,9,9,9,6},{62,65,81,33,94},{127,9,25,41,70},{70,73,73,73,49},{1,1,127,1,1},{63,64,64,64,63},{31,32,64,32,31},{127,32,24,32,127},{99,20,8,20,99},{3,4,120,4,3},{97,81,73,69,67}};
  if(c>='A'&&c<='Z') return az[c-'A']; if(c>='0'&&c<='9') return nums[c-'0'];
  static const uint8_t dash[5]={8,8,8,8,8}, dot[5]={0,96,96,0,0}, colon[5]={0,54,54,0,0};
  if(c=='-') return dash; if(c=='.') return dot; if(c==':') return colon; return blank;
}
void text(int x,int y,const char*s,uint16_t c,int scale=1) {
  while(*s){ const uint8_t*g=glyph(toupper(*s++)); for(int a=0;a<5;a++) for(int b=0;b<7;b++) if(g[a]&(1<<b)) rect(x+a*scale,y+b*scale,scale,scale,c); x+=6*scale; }
}
int textWidth(const char*s,int scale){return strlen(s)*6*scale-scale;}
void centered(int y,const char*s,uint16_t c,int scale=1){text((W-textWidth(s,scale))/2,y,s,c,scale);}

void drawMagnifier(int x,int y,uint16_t c){circle(x,y,12,c);line(x+9,y+9,x+23,y+23,c,4);}
void drawFace(uint8_t v, bool talking) {
  const uint32_t t=millis();
  const int cx=W/2, cy=119+(int)(2*sinf(t/650.0f));
  const bool thinking=currentState==DetectiveScreenState::Deducing;
  const bool solved=currentState==DetectiveScreenState::Printing;
  const bool blink=t%4300<135;
  // Oversized cut-paper face; a restrained deerstalker identifies the character.
  // Rough, mismatched contours and pin pupils give this original detective
  // a scruffy sci-fi cartoon character rather than a polished emoji face.
  for(int side=-1;side<=1;side+=2){
    for(int i=0;i<5;i++)line(cx+side*68,cy-23+i*12,cx+side*(91+(i%2)*8),cy-35+i*13,INK,10);
    for(int i=0;i<5;i++)line(cx+side*68,cy-23+i*12,cx+side*(91+(i%2)*8),cy-35+i*13,HAIR,5);
  }
  oval(cx-2,cy+12,87,77,INK); oval(cx-3,cy+10,82,72,SKIN);
  oval(cx,cy-62,67,33,INK);
  rect(cx-67,cy-60,134,12,INK);
  line(cx-84,cy-47,cx+84,cy-47,INK,9);
  line(cx,cy-91,cx-5,cy-56,MUTED,3);
  line(cx-38,cy-81,cx-31,cy-57,MUTED,2);
  line(cx+38,cy-81,cx+31,cy-57,MUTED,2);
  const int look=thinking?(int)(6*sinf(t/1150.0f)):2;
  for(int side=-1;side<=1;side+=2){
    const int ex=cx+side*35;
    if(blink) line(ex-16,cy-2,ex+16,cy-2,INK,5);
    else {
      oval(ex,cy+(side<0?-3:2),25,side<0?27:23,INK);
      oval(ex,cy+(side<0?-3:2),22,side<0?24:20,WHITE);
      oval(ex+look,cy+3,4,5,INK);
      if(thinking){rect(ex-22,cy-23,44,12,SKIN);line(ex-21,cy-10,ex+21,cy-13,INK,3);}
    }
    const int tilt=(thinking || v%3==1)?side*7:solved?-side*5:side*3;
    line(ex-21,cy-32-tilt,ex+18,cy-30+tilt,INK,5);
  }
  // Monocle and warm cheek marks remain inside the rounded-panel safe area.
  circle(cx+35,cy,31,MUTED); line(cx+66,cy+6,cx+73,cy+38,MUTED,2);
  line(cx-3,cy+6,cx-8,cy+21,INK,2);line(cx-8,cy+21,cx+5,cy+23,INK,2);
  for(int i=0;i<4;i++){line(cx-54+i*7,cy+49+i%2*5,cx-52+i*7,cy+53+i%2*5,INK,2);}
  if(talking){
    int open=5+(int)(12*fabsf(sinf(t/115.0f)));
    oval(cx+3,cy+43,26,open,INK);
    if(open>10){
      oval(cx+7,cy+49,13,4,RED);
      for(int i=0;i<4;i++)rect(cx-15+i*9,cy+43-open+2,7,5+i%2*2,WHITE);
    }
  } else if(thinking){
    line(cx-14,cy+44,cx+13,cy+40,INK,4);
  } else {
    line(cx-18,cy+37,cx-7,cy+47,INK,4);
    line(cx-7,cy+47,cx+9,cy+48,INK,4);
    line(cx+9,cy+48,cx+22,cy+36,INK,4);
  }
}

const char* titleFor(DetectiveScreenState s){
  switch(s){case DetectiveScreenState::Boot:return "OPENING CASE";case DetectiveScreenState::Setup:return "NETWORK CLUE";case DetectiveScreenState::Ready:return "CASE DESK READY";case DetectiveScreenState::Capturing:return "SCENE CAPTURED";case DetectiveScreenState::Deducing:return "DEDUCING";case DetectiveScreenState::Printing:return "REPORT IN MOTION";default:return "PLOT COMPLICATION";}
}
const char* subFor(DetectiveScreenState s){
  switch(s){case DetectiveScreenState::Boot:return "DASHAN DETECTIVE CAMERA";case DetectiveScreenState::Setup:return "CONNECT TO THE DIRECTOR";case DetectiveScreenState::Ready:return "PRESS SHUTTER. ACT INNOCENT.";case DetectiveScreenState::Capturing:return "DO NOT DISTURB THE EVIDENCE";case DetectiveScreenState::Deducing:return "FACTS FIRST. NONSENSE SECOND.";case DetectiveScreenState::Printing:return "TAKE THE PAPER. NOT THE CREDIT.";default:return "CHECK POWER AND CONNECTIONS";}
}
void render(bool talking=false) {
  if(!ready) return;
  fill(SPACE);
  line(20,25,W-20,25,GOLD,1);
  text(22,12,"DASHAN / ODD CASES",GOLD,1);
  circle(W-24,15,3,connected?0x35A8:RED,true);
  if(currentState==DetectiveScreenState::Boot || currentState==DetectiveScreenState::Setup || currentState==DetectiveScreenState::Error){
    drawMagnifier(W/2-10,123,INK);
    centered(188,titleFor(currentState),WHITE,1);
    centered(215,currentState==DetectiveScreenState::Error?"PLEASE CHECK CONNECTION":"CONNECTING",WHITE,1);
  }else if(currentState==DetectiveScreenState::Ready){
    centered(135,"OPENING VIEWFINDER",WHITE,1);
  }else{
    // An irregular acid-green field frames the face; it does not flash.
    oval(W/2,124,113,83,0x246B);
    for(int i=0;i<9;i++){
      float a=i*0.698f;
      int x=W/2+(int)(106*cosf(a)),y=124+(int)(75*sinf(a));
      line(x,y,x+5,y-7,GOLD,3);
    }
    drawFace(faceVariant,talking);
    centered(219,currentState==DetectiveScreenState::Capturing?"SCENE RECEIVED":currentState==DetectiveScreenState::Printing?"CASE RECONSTRUCTION":"EXAMINING THE CLUES",WHITE,1);
    for(int i=0;i<3;i++)circle(W/2-12+i*12,233,2,(millis()/420)%3==i?RED:GOLD,true);
  }
  present();
}
bool ioxWrite(uint8_t reg,uint8_t value){
  BoardI2cGuard lock;
  // The on-board CH32V003 can become I2C-ready noticeably later than the
  // ESP32 during a true power-on reset. USB flashing hid this race by keeping
  // the board powered. Retry so battery/cold boots are deterministic.
  for(uint8_t attempt=0;attempt<20;attempt++){
    Wire.beginTransmission(IOX);Wire.write(reg);Wire.write(value);
    if(Wire.endTransmission()==0)return true;
    delay(25);
  }
  return false;
}
}

bool detectiveDisplayBegin(){
  canvas=(uint16_t*)heap_caps_malloc(W*H*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT); if(!canvas) canvas=(uint16_t*)malloc(W*H*2); if(!canvas)return false;
  dmaStrip=(uint16_t*)heap_caps_malloc(W*16*2,MALLOC_CAP_DMA|MALLOC_CAP_INTERNAL);if(!dmaStrip)return false;
  // Give the CH32 power/IO controller and LCD rail time to settle on a real
  // cold start. A warm USB reset does not require this delay but tolerates it.
  delay(350);
  // Match the board BSP's output mask; EXIO6 is the power LED, not an LCD
  // power switch. Keep SD CS/camera control high and the amplifier disabled.
  if(!ioxWrite(0x02,0x77))return false;
  if(!ioxWrite(0x03,0x64))return false;   // touch/LCD resets asserted
  delay(120);
  if(!ioxWrite(0x03,0x67))return false;   // release touch/LCD resets
  delay(120);
  spi_bus_config_t bus={}; bus.sclk_io_num=PIN_CLK;bus.mosi_io_num=PIN_MOSI;bus.miso_io_num=-1;bus.quadwp_io_num=-1;bus.quadhd_io_num=-1;bus.max_transfer_sz=W*H*2;
  if(spi_bus_initialize(SPI2_HOST,&bus,SPI_DMA_CH_AUTO)!=ESP_OK)return false;
  frameDone=xSemaphoreCreateBinary(); if(!frameDone)return false;
  esp_lcd_panel_io_spi_config_t io={};io.dc_gpio_num=PIN_DC;io.cs_gpio_num=PIN_CS;io.pclk_hz=40000000;io.lcd_cmd_bits=8;io.lcd_param_bits=8;io.spi_mode=0;io.trans_queue_depth=2;io.on_color_trans_done=onFrameDone;
  if(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)SPI2_HOST,&io,&panelIo)!=ESP_OK)return false;
  esp_lcd_panel_dev_config_t cfg={};cfg.reset_gpio_num=-1;cfg.rgb_ele_order=LCD_RGB_ELEMENT_ORDER_RGB;cfg.bits_per_pixel=16;
  if(esp_lcd_new_panel_st7789(panelIo,&cfg,&panel)!=ESP_OK)return false;
  esp_lcd_panel_reset(panel);esp_lcd_panel_init(panel);
  esp_lcd_panel_disp_on_off(panel,false);
  esp_lcd_panel_invert_color(panel,true);
  esp_lcd_panel_swap_xy(panel,true);esp_lcd_panel_mirror(panel,true,false);
  // Waveshare's 1.83-inch BSP uses a zero-origin 284x240 landscape window,
  // not a centered 18-pixel crop of the ST7789's 320-column RAM.
  if(esp_lcd_panel_set_gap(panel,0,0)!=ESP_OK)return false;
  // Clear all controller RAM before showing the first frame, including the
  // unused columns. Eight 320-pixel rows fit the existing small DMA buffer.
  memset(dmaStrip,0,320*8*sizeof(uint16_t));
  for(int y=0;y<H;y+=8){
    if(esp_lcd_panel_draw_bitmap(panel,0,y,320,y+8,dmaStrip)!=ESP_OK)return false;
    xSemaphoreTake(frameDone,portMAX_DELAY);
  }
  ready=true;render();
  if(esp_lcd_panel_disp_on_off(panel,true)!=ESP_OK){ready=false;return false;}
  if(!ioxWrite(0x05,247)){ready=false;return false;} // enable backlight last
  Serial.println("display: landscape 284x240 origin=0,0 RAM cleared");
  return true;
}
void detectiveDisplaySetState(DetectiveScreenState s,const char*detail){currentState=s;}
void detectiveDisplaySetConnected(bool value){connected=value;}
void detectiveDisplayRequestSelfTest(){selfTestRequested=true;}
void detectiveDisplayService(bool voicePlaying){
  if(!ready)return;
  if(!displayOwner)displayOwner=xTaskGetCurrentTaskHandle();
  if(displayOwner!=xTaskGetCurrentTaskHandle())return;
  if(selfTestRequested){
    selfTestRequested=false;
    // All SPI drawing stays on the display owner; each prior DMA strip has
    // completed before resetting. Preserve the running audio amplifier.
    bool ok=ioxWrite(0x02,0x77) && ioxWrite(0x03,0x75);
    delay(50);
    ok=ioxWrite(0x03,0x77) && ok;
    delay(150);
    ok=(esp_lcd_panel_reset(panel)==ESP_OK) && ok;
    ok=(esp_lcd_panel_init(panel)==ESP_OK) && ok;
    ok=(esp_lcd_panel_invert_color(panel,true)==ESP_OK) && ok;
    ok=(esp_lcd_panel_swap_xy(panel,true)==ESP_OK) && ok;
    ok=(esp_lcd_panel_mirror(panel,true,false)==ESP_OK) && ok;
    ok=(esp_lcd_panel_set_gap(panel,0,0)==ESP_OK) && ok;
    ok=(esp_lcd_panel_disp_on_off(panel,true)==ESP_OK) && ok;
    ok=ioxWrite(0x05,247) && ok;
    rect(0,0,W/3,H,0xF800);rect(W/3,0,W/3,H,0x07E0);
    rect(2*(W/3),0,W-2*(W/3),H,0x001F);
    ok=present() && ok;
    Serial.printf("display: self-test commands=%s RGB bars 3s (visual confirmation required)\n",ok?"ok":"failed");
    delay(3000);
    render();
  }
  uint32_t now=millis();
  if(now-lastFrame<66)return;
  lastFrame=now;
  if(currentState==DetectiveScreenState::Ready)return;
  faceVariant=now/3400;
  render(voicePlaying);
}
bool detectiveDisplayStandby(){
  // Preserve EXIO5 (BAT_EN); only blank the panel and mute the amplifier.
  if(!ioxWrite(0x05,0))return false;
  if(panel && esp_lcd_panel_disp_on_off(panel,false)!=ESP_OK)return false;
  return ioxWrite(0x03,0x67);
}
bool detectiveDisplayReady(){return ready;}
bool detectiveDisplayWantsPreview(){return ready && currentState==DetectiveScreenState::Ready;}
bool detectiveDisplayPreview(const uint8_t *jpeg,size_t length,int width,int height){
  if(!detectiveDisplayWantsPreview() || width<=0 || height<=0 || width>4096 || height>4096)return false;
  int divisor=1, scale=0;
  while(scale<3 && width/(divisor*2)>=W){divisor*=2;scale++;}
  int dw=(width+divisor-1)/divisor, dh=(height+divisor-1)/divisor;
  size_t required=(size_t)dw*dh*3;
  if(required>decodedCapacity){
    uint8_t *next=(uint8_t*)heap_caps_malloc(required,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!next)return false;
    free(decoded);decoded=next;decodedCapacity=required;
  }
  esp_jpeg_image_cfg_t cfg={};
  cfg.indata=const_cast<uint8_t*>(jpeg);cfg.indata_size=length;
  cfg.outbuf=decoded;cfg.outbuf_size=decodedCapacity;
  cfg.out_format=JPEG_IMAGE_FORMAT_RGB888;cfg.out_scale=(esp_jpeg_image_scale_t)scale;
  esp_jpeg_image_output_t output={};
  if(esp_jpeg_decode(&cfg,&output)!=ESP_OK)return false;
  dw=output.width;dh=output.height;
  if(!dw || !dh)return false;
  if(!detectiveDisplayWantsPreview())return false;
  fill(BLACK);
  // Contain the full photo; no stretching or hidden evidence at the edges.
  int vw=W,vh=dh*W/dw;
  if(vh>H-52){vh=H-52;vw=dw*vh/dh;}
  const int ox=(W-vw)/2,oy=(H-vh)/2;
  for(int y=0;y<vh;y++)for(int x=0;x<vw;x++){
    size_t p=((size_t)(y*dh/vh)*dw+x*dw/vw)*3;
    px(ox+x,oy+y,((decoded[p]&0xF8)<<8)|((decoded[p+1]&0xFC)<<3)|(decoded[p+2]>>3));
  }
  text(20,17,"LIVE",GOLD,1);circle(W-22,20,3,connected?GOLD:RED,true);
  centered(H-23,"PRESS SHUTTER",WHITE,1);
  const int l=12;
  for(int i=0;i<2;i++)for(int j=0;j<2;j++){
    int x=ox+10+i*(vw-21),y=oy+10+j*(vh-21);
    line(x,y,x+(i?-l:l),y,GOLD,2);line(x,y,x,y+(j?-l:l),GOLD,2);
  }
  return present();
}
