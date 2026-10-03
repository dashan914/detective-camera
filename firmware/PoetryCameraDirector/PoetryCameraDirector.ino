#include <Arduino.h>
#include <Audio.h>
#include <DNSServer.h>
#include <FFat.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <Wire.h>
#include <WebServer.h>
#include <WiFi.h>
#include "esp_camera.h"
#include "DetectiveDisplay.h"
#include "es8311.h"

// Waveshare ESP32-S3-CAM-OV5640 pin map from the board documentation.
// PWDN is controlled by the on-board IO expander; -1 keeps the board default.
static constexpr int CAM_D0 = 45, CAM_D1 = 47, CAM_D2 = 48, CAM_D3 = 46;
static constexpr int CAM_D4 = 42, CAM_D5 = 40, CAM_D6 = 39, CAM_D7 = 21;
static constexpr int CAM_PCLK = 41, CAM_VSYNC = 17, CAM_HREF = 18;
static constexpr int CAM_XCLK = 38, CAM_SDA = 8, CAM_SCL = 7;
static constexpr int PRINTER_TX = 43, PRINTER_RX = 44;
static constexpr int SETUP_BUTTON = 0;
static constexpr int AUDIO_MCLK = 10, AUDIO_BCLK = 11, AUDIO_LRCK = 12, AUDIO_DOUT = 14;
// Address verified on the connected Waveshare expansion board (A2:A0=111).
static constexpr uint8_t SHUTTER_MCP_ADDR = 0x27;
static constexpr uint8_t SHUTTER_GPIOB_REG = 0x13;
static constexpr uint32_t SHUTTER_DEBOUNCE_MS = 20;
static constexpr uint32_t PRINTER_BAUD = 9600;

Preferences prefs;
WebServer setupServer(80);
DNSServer dnsServer;
HardwareSerial printer(1);
volatile bool printerBusy = false;
static String activePrintJob;

enum class VoiceStage : uint8_t { Capture, Waiting, LongWait, PrintStart, Error };

struct VoiceCommand {
  VoiceStage stage;
  bool interrupt;
  bool narration;
};

Audio voiceAudio;
ES8311 voiceCodec;
QueueHandle_t voiceQueue = nullptr;
TaskHandle_t voiceTaskHandle = nullptr;
bool voiceReady = false;
bool voiceFsReady = false;
bool voiceCodecReady = false;
bool voiceAmpReady = false;
// Accessed by loop() only as a completion flag; voiceAudio itself remains
// exclusively owned by voiceTask().  0=idle, 1=queued, 2=playing, 3=done,
// 4=failed.
volatile uint8_t caseNarrationState = 0;
volatile bool caseNarrationSawRunning = false;
volatile bool voiceAudioPlaying = false;
volatile bool caseNarrationCancel = false;
extern uint32_t lastHeartbeat;
static void sendHeartbeat();
extern String backendUrl, deviceToken, deviceId;
volatile bool investigationActive = false;
volatile bool synchronizedPrint = false;
// 0 idle, 1 queued, 2 playing, 3 fully drained, 4 failed.
volatile uint8_t reportAnnouncementState = 0;
volatile bool reportAnnouncementSawRunning = false;
volatile uint32_t reportAnnouncementStartedAt = 0;
// Only guard against the decoder's brief startup false-idle window.  The
// actual release condition remains: playback has really run, then stopped,
// and the I2S buffer has drained.
static constexpr uint32_t kReportAnnouncementMinimumMs = 900;
uint32_t voiceTestEnd = 0;
bool voiceTestNarration = false;
uint32_t investigationStarted = 0;
uint32_t nextWaitingVoice = 0;
uint8_t waitingVoiceCount = 0;
uint8_t recentVoices[3] = {};
uint8_t recentVoicePos = 0;
bool shutterReady = false;
bool shutterRawPressed = false;
bool shutterStablePressed = false;
bool shutterArmed = true;
uint32_t shutterChangedAt = 0;
volatile bool standbyRequested = false;
volatile bool standbyDisplayDone = false;
volatile bool standbyVoiceDone = false;
bool standbyActive = false;
bool shutterLongHandled = false;
uint32_t shutterPressedAt = 0;
QueueHandle_t shutterEvents = nullptr;
TaskHandle_t shutterTaskHandle = nullptr;
SemaphoreHandle_t boardI2cMutex = nullptr;
volatile bool shutterSamplingEnabled = false;
static void servicePhysicalShutter();

static void executeJob(const String &json);

static void voiceRange(VoiceStage stage, uint8_t &first, uint8_t &last, const char *&suffix) {
  switch (stage) {
    case VoiceStage::Capture: first = 1; last = 4; suffix = "shutter"; break;
    case VoiceStage::Waiting: first = 5; last = 8; suffix = "wait"; break;
    case VoiceStage::LongWait: first = 5; last = 8; suffix = "wait"; break;
    case VoiceStage::PrintStart: first = 9; last = 12; suffix = "printing"; break;
    default: first = 73; last = 80; suffix = "error"; break;
  }
}

static bool wasRecentlyPlayed(uint8_t number) {
  for (uint8_t recent : recentVoices) if (recent == number) return true;
  return false;
}

static String chooseVoiceFile(VoiceStage stage) {
  if (stage == VoiceStage::PrintStart && FFat.exists("/voice/report.mp3")) return "/voice/report.mp3";
  uint8_t first, last;
  const char *suffix;
  voiceRange(stage, first, last, suffix);
  uint8_t number = first;
  for (uint8_t attempt = 0; attempt < 32; attempt++) {
    number = first + (esp_random() % (last - first + 1));
    if (!wasRecentlyPlayed(number)) break;
  }
  recentVoices[recentVoicePos] = number;
  recentVoicePos = (recentVoicePos + 1) % (sizeof(recentVoices) / sizeof(recentVoices[0]));
  char path[40];
  snprintf(path, sizeof(path), "/voice/%02u_%s.mp3", number, suffix);
  // The installed 12-clip FAT image retained the former 80-slot names:
  // thinking clips start at 13 and report clips at 57. Prefer native names
  // when available; otherwise map the four choices to their installed slots.
  if (!FFat.exists(path)) {
    if (stage == VoiceStage::Waiting || stage == VoiceStage::LongWait)
      snprintf(path, sizeof(path), "/voice/%02u_wait.mp3", 13 + (number - 5));
    else if (stage == VoiceStage::PrintStart)
      snprintf(path, sizeof(path), "/voice/%02u_printing.mp3", 57 + (number - 9));
  }
  return String(path);
}

static void voiceTask(void *) {
  VoiceCommand command;
  VoiceCommand pending{};
  bool hasPending = false;
  uint32_t idleSince = 0;
  uint32_t drainMs = 230;
  for (;;) {
    if(standbyRequested){
      voiceAudio.stopSong();
      hasPending=false;
      xQueueReset(voiceQueue);
      voiceAudioPlaying=false;
      standbyVoiceDone=true;
      while(standbyRequested)vTaskDelay(pdMS_TO_TICKS(20));
      standbyVoiceDone=false;
    }
    if (!hasPending && xQueueReceive(voiceQueue, &command, 0) == pdTRUE) {
      pending = command;
      hasPending = true;
    }
    if (caseNarrationCancel) {
      if (caseNarrationState == 2) {
        voiceAudio.stopSong();
      } else if (hasPending && pending.narration) {
        hasPending = false;
      }
      if (caseNarrationState == 2 || (caseNarrationState == 1 && !hasPending)) {
        caseNarrationState = 4;
        caseNarrationCancel = false;
      }
    }
    // Discard an unstarted thinking line before playback when the result is
    // ready; the line already speaking is allowed to finish naturally.
    if (hasPending && !pending.narration && pending.stage == VoiceStage::Waiting && !investigationActive) hasPending = false;
    const bool drained = !voiceAudio.isRunning() && millis() - idleSince >= drainMs;
    const uint32_t breathMs = hasPending && !pending.narration ?
        (pending.stage == VoiceStage::Waiting ? 400 : pending.stage == VoiceStage::PrintStart ? 1000 : 100) : 100;
    if (hasPending && voiceReady && (pending.interrupt || (drained && millis() - idleSince >= drainMs + breathMs))) {
      if (pending.interrupt) voiceAudio.stopSong();
      String path = pending.narration ? String("/case-narration.mp3") : chooseVoiceFile(pending.stage);
      bool ok = FFat.exists(path) && voiceAudio.connecttoFS(FFat, path.c_str());
      if (ok) idleSince = millis();
      Serial.printf("voice: t=%u %s %s active=%d\n", millis(), ok ? "play" : "open_failed", path.c_str(), investigationActive);
      if (pending.narration) {
        caseNarrationSawRunning = false;
        caseNarrationState = ok ? 2 : 4;
      } else if (pending.stage == VoiceStage::PrintStart) {
        reportAnnouncementSawRunning = false;
        reportAnnouncementStartedAt = ok ? millis() : 0;
        reportAnnouncementState = ok ? 2 : 4;
      }
      hasPending = false;
    }
    if (caseNarrationState == 2 && voiceAudio.isRunning()) caseNarrationSawRunning = true;
    if (caseNarrationState == 2 && caseNarrationSawRunning && !voiceAudio.isRunning() && millis() - idleSince >= drainMs) {
      caseNarrationState = 3;
      // The speaker has drained the final samples. Restore the viewfinder
      // here, without waiting for paper feed or a blocking HTTP completion.
      detectiveDisplaySetState(DetectiveScreenState::Ready);
      Serial.println("display: narration finished -> live preview (printer independent)");
    }
    if (reportAnnouncementState == 2 && voiceAudio.isRunning()) reportAnnouncementSawRunning = true;
    if (reportAnnouncementState == 2 && reportAnnouncementSawRunning &&
        !voiceAudio.isRunning() && millis() - idleSince >= drainMs &&
        millis() - reportAnnouncementStartedAt >= kReportAnnouncementMinimumMs) {
      reportAnnouncementState = 3;
      Serial.printf("voice: report fully finished t=%u elapsed=%u\n", millis(), millis() - reportAnnouncementStartedAt);
    }
    if (voiceReady) voiceAudio.loop();
    voiceAudioPlaying = voiceReady && voiceAudio.isRunning();
    if (voiceAudioPlaying) {
      idleSince = millis();
      uint32_t rate = voiceAudio.getSampleRate();
      if (rate) drainMs = (8192UL * 1000UL + rate - 1) / rate + 40;
    }
    if (investigationActive && voiceReady && !voiceAudioPlaying && !hasPending &&
        uxQueueMessagesWaiting(voiceQueue) == 0 && millis() - idleSince >= drainMs + 400) {
      pending = VoiceCommand{VoiceStage::Waiting, false, false};
      hasPending = true;
    }
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}

static void startVoiceSystem() {
  voiceFsReady = FFat.begin(false);
  if (!voiceFsReady) {
    Serial.println(F("voice: FFat mount failed (upload voice filesystem first)"));
    return;
  }
  // ES8311 and camera share the board I2C bus on GPIO 8/7.
  voiceCodecReady = voiceCodec.begin(CAM_SDA, CAM_SCL, 400000);
  voiceCodecReady &= voiceCodec.setVolume(72);
  voiceCodecReady &= voiceCodec.setBitsPerSample(16);
  // The board's NS4150B speaker amplifier enable is CH32V003 EXIO4.
  // Waveshare's Arduino audio-out example enables it with a HIGH level.
  Wire.beginTransmission(0x24);
  Wire.write(0x02);  // CH32 direction register
  Wire.write(0x77);  // EXIO0/1/2/4/5/6 outputs
  const bool directionOk = Wire.endTransmission() == 0;
  Wire.beginTransmission(0x24);
  Wire.write(0x03);  // CH32 output register
  Wire.write(0x77);  // EXIO4=1 (PA enabled), other required rails high
  const bool outputOk = Wire.endTransmission() == 0;
  voiceAmpReady = directionOk && outputOk;
  voiceReady = voiceCodecReady && voiceAmpReady;
  voiceReady &= voiceAudio.setPinout(AUDIO_BCLK, AUDIO_LRCK, AUDIO_DOUT, AUDIO_MCLK);
  voiceAudio.setVolume(21);  // Decoder-side scale: 0..21.
  Serial.printf("voice: %s codec=%d amp=%d FFat=%u/%u bytes\n",
                voiceReady ? "ready" : "init_failed", voiceCodecReady, voiceAmpReady,
                (unsigned)FFat.usedBytes(), (unsigned)FFat.totalBytes());
  if (!voiceReady) return;
  voiceQueue = xQueueCreate(6, sizeof(VoiceCommand));
  if (!voiceQueue) {
    Serial.println(F("voice: queue allocation failed"));
    return;
  }
  xTaskCreatePinnedToCore(voiceTask, "voice", 12288, nullptr, 2, &voiceTaskHandle, 0);
}

static void requestVoice(VoiceStage stage, bool interrupt = false) {
  if (!voiceQueue || stage == VoiceStage::Error) return;
  VoiceCommand command{stage, interrupt, false};
  if (interrupt) xQueueReset(voiceQueue);
  xQueueSend(voiceQueue, &command, 0);
}

static bool requestCaseNarrationVoice() {
  if (!voiceQueue || !voiceReady || !FFat.exists("/case-narration.mp3")) return false;
  VoiceCommand command{VoiceStage::Waiting, false, true};
  caseNarrationSawRunning = false;
  caseNarrationCancel = false;
  caseNarrationState = 1;
  if (xQueueSend(voiceQueue, &command, 0) != pdTRUE) {
    caseNarrationState = 4;
    return false;
  }
  return true;
}

static bool downloadCaseNarration(const String &jobId, String &detail) {
  static constexpr size_t MAX_AUDIO_BYTES = 1024 * 1024;
  const char *tmpPath = "/case-narration.tmp";
  const char *finalPath = "/case-narration.mp3";
  if (!voiceFsReady) { detail = "voice_fs_not_ready"; return false; }
  FFat.remove(tmpPath);
  HTTPClient http;
  http.begin(backendUrl + "/api/device/jobs/" + jobId + "/audio-data");
  http.setTimeout(60000);
  http.addHeader("X-Dashan-Token", deviceToken);
  http.addHeader("X-Dashan-Device", deviceId);
  int code = http.GET();
  if (code != 200) {
    detail = String("audio_data_http_") + code;
    http.end();
    return false;
  }
  int contentLength = http.getSize();
  if (contentLength > (int)MAX_AUDIO_BYTES) {
    detail = "audio_data_too_large";
    http.end();
    return false;
  }
  File out = FFat.open(tmpPath, FILE_WRITE);
  if (!out) {
    detail = "audio_temp_open_failed";
    http.end();
    return false;
  }
  WiFiClient *stream = http.getStreamPtr();
  uint8_t buffer[1024];
  size_t received = 0;
  uint32_t started = millis();
  bool ok = true;
  while (http.connected() && (contentLength < 0 || received < (size_t)contentLength)) {
    if (millis() - started > 60000) { ok = false; detail = "audio_data_timeout"; break; }
    size_t available = stream->available();
    if (!available) { delay(2); continue; }
    size_t take = min(available, sizeof(buffer));
    if (contentLength >= 0) take = min(take, (size_t)contentLength - received);
    int got = stream->readBytes(buffer, take);
    if (got <= 0 || received + (size_t)got > MAX_AUDIO_BYTES || out.write(buffer, got) != (size_t)got) {
      ok = false; detail = "audio_data_write_failed"; break;
    }
    received += got;
  }
  out.close();
  http.end();
  if (!ok || received == 0 || (contentLength >= 0 && received != (size_t)contentLength)) {
    if (detail.length() == 0) detail = "audio_data_incomplete";
    FFat.remove(tmpPath);
    return false;
  }
  // Only replace the prior case narration after a complete bounded download.
  FFat.remove(finalPath);
  if (!FFat.rename(tmpPath, finalPath)) {
    detail = "audio_final_rename_failed";
    FFat.remove(tmpPath);
    return false;
  }
  detail = String("audio_bytes_") + received;
  return true;
}

static bool playCaseNarration(const String &jobId, String &detail) {
  if (!requestCaseNarrationVoice()) { detail = "narration_queue_failed"; return false; }
  const uint32_t started = millis();
  while (caseNarrationState == 1 || caseNarrationState == 2) {
    detectiveDisplayService(voiceAudioPlaying);
    if (millis() - lastHeartbeat >= 15000UL) {
      lastHeartbeat = millis();
      sendHeartbeat();
    }
    if (millis() - started > 180000UL) {
      caseNarrationCancel = true;
      detail = "narration_timeout";
      return false;
    }
    delay(10); // voiceTask continues on its pinned core
  }
  if (caseNarrationState != 3) { detail = "narration_open_failed"; return false; }
  detail = String("narration_played_") + jobId;
  return true;
}

static void beginInvestigationVoices() {
  investigationActive = true;
  investigationStarted = millis();
  waitingVoiceCount = 0;
  nextWaitingVoice = investigationStarted + 5000;
}

static void finishInvestigationVoices(VoiceStage finalStage) {
  investigationActive = false;
  requestVoice(finalStage, true);
}

static void serviceInvestigationVoices() {
  // The audio task schedules the next line at playback completion, including
  // while the main task is uploading a photo or downloading narration.
}

String wifiSsid, wifiPassword, backendUrl, deviceToken, deviceId;
bool setupMode = false;
bool cameraReady = false;
SemaphoreHandle_t cameraMutex = nullptr;
bool cameraPreviewMode = false;
TaskHandle_t displayTaskHandle = nullptr;
struct CameraGuard {
  CameraGuard(){if(cameraMutex)xSemaphoreTakeRecursive(cameraMutex,portMAX_DELAY);}
  ~CameraGuard(){if(cameraMutex)xSemaphoreGiveRecursive(cameraMutex);}
};
static void displayTask(void *) {
  uint32_t previousPreview=0;
  uint32_t lastStats=millis(),previewFrames=0,previewErrors=0;
  for(;;){
    if(standbyRequested){
      if(!standbyDisplayDone)standbyDisplayDone=detectiveDisplayStandby();
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    detectiveDisplayService(voiceAudioPlaying);
    // One owner for drawing; preview never changes the sensor resolution.
    if(cameraReady && detectiveDisplayWantsPreview() && millis()-previousPreview>=120 &&
       xSemaphoreTakeRecursive(cameraMutex,0)==pdTRUE){
      previousPreview=millis();
      if(!cameraPreviewMode){
        sensor_t *sensor=esp_camera_sensor_get();
        if(sensor){sensor->set_framesize(sensor,FRAMESIZE_QVGA);sensor->set_quality(sensor,24);cameraPreviewMode=true;}
        for(int n=0;n<2;n++){camera_fb_t *old=esp_camera_fb_get();if(old)esp_camera_fb_return(old);}
      }
      camera_fb_t *frame=esp_camera_fb_get();
      if(frame){
        if(detectiveDisplayPreview(frame->buf,frame->len,frame->width,frame->height))previewFrames++;
        else previewErrors++;
        esp_camera_fb_return(frame);
      }
      xSemaphoreGiveRecursive(cameraMutex);
    }
    if(millis()-lastStats>=10000){
      Serial.printf("display: preview_frames=%u errors=%u window_ms=%u\n",previewFrames,previewErrors,millis()-lastStats);
      lastStats=millis();previewFrames=0;previewErrors=0;
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}
uint32_t lastHeartbeat = 0, lastPoll = 0;
uint32_t lastSetupLog = 0;
uint32_t cameraRevision = 0;
String cameraSettingsJson;

static String htmlEscape(const String &s) {
  String out;
  out.reserve(s.length() + 16);
  for (char c : s) {
    if (c == '&') out += F("&amp;");
    else if (c == '<') out += F("&lt;");
    else if (c == '>') out += F("&gt;");
    else if (c == '\"') out += F("&quot;");
    else out += c;
  }
  return out;
}

static String jsonEscape(const String &s) {
  String out;
  out.reserve(s.length() + 16);
  for (char c : s) {
    if (c == '\\' || c == '\"') { out += '\\'; out += c; }
    else if (c == '\n') out += F("\\n");
    else if (c == '\r') out += F("\\r");
    else if ((uint8_t)c >= 0x20) out += c;
  }
  return out;
}

// Minimal JSON string reader for the small, controlled device-job response.
static String jsonString(const String &json, const char *key) {
  String needle = String('"') + key + F("\"");
  int p = json.indexOf(needle);
  if (p < 0) return "";
  p = json.indexOf(':', p + needle.length());
  if (p < 0) return "";
  p++;
  while (p < (int)json.length() && isspace((unsigned char)json[p])) p++;
  if (p >= (int)json.length() || json[p] != '"') return "";
  p++;
  String out;
  bool escaped = false;
  for (; p < (int)json.length(); p++) {
    char c = json[p];
    if (escaped) {
      if (c == 'n') out += '\n'; else if (c == 'r') out += '\r'; else out += c;
      escaped = false;
    } else if (c == '\\') escaped = true;
    else if (c == '"') break;
    else out += c;
  }
  return out;
}

static int jsonInt(const String &json, const char *key, int fallback) {
  String needle = String('"') + key + F("\"");
  int p = json.indexOf(needle);
  if (p < 0 || (p = json.indexOf(':', p + needle.length())) < 0) return fallback;
  p++; while (p < (int)json.length() && isspace((unsigned char)json[p])) p++;
  return json.substring(p).toInt();
}

static bool jsonBool(const String &json, const char *key, bool fallback) {
  String needle = String('"') + key + F("\"");
  int p = json.indexOf(needle);
  if (p < 0 || (p = json.indexOf(':', p + needle.length())) < 0) return fallback;
  p++; while (p < (int)json.length() && isspace((unsigned char)json[p])) p++;
  if (json.startsWith("true", p)) return true;
  if (json.startsWith("false", p)) return false;
  return fallback;
}

static framesize_t frameSize(const String &name) {
  if (name == "SVGA") return FRAMESIZE_SVGA;
  if (name == "XGA") return FRAMESIZE_XGA;
  if (name == "SXGA") return FRAMESIZE_SXGA;
  return FRAMESIZE_UXGA;
}

static void applyCameraSettings(const String &json) {
  CameraGuard guard;
  uint32_t revision = (uint32_t)jsonInt(json, "revision", cameraRevision);
  if (!cameraReady || revision == 0 || revision == cameraRevision) return;
  sensor_t *s = esp_camera_sensor_get();
  if (!s) return;
  String size = jsonString(json, "frame_size");
  s->set_framesize(s, frameSize(size));
  s->set_quality(s, jsonInt(json, "jpeg_quality", 12));
  s->set_brightness(s, jsonInt(json, "brightness", 0));
  s->set_contrast(s, jsonInt(json, "contrast", 0));
  s->set_saturation(s, jsonInt(json, "saturation", 0));
  s->set_ae_level(s, jsonInt(json, "exposure", 0));
  String whiteBalance = jsonString(json, "white_balance");
  bool autoWhiteBalance = whiteBalance.length() == 0 || whiteBalance == "auto";
  s->set_whitebal(s, autoWhiteBalance ? 1 : 0);
  if (!autoWhiteBalance) {
    int mode = whiteBalance == "cloudy" ? 1 : whiteBalance == "office" ? 2 : whiteBalance == "home" ? 3 : 0;
    s->set_wb_mode(s, mode);
  }
  s->set_hmirror(s, jsonBool(json, "mirror", false));
  s->set_vflip(s, jsonBool(json, "flip", false));
  cameraRevision = revision;
  cameraPreviewMode = false;
  Serial.printf("camera settings applied: revision=%u frame=%s\n", cameraRevision, size.c_str());
}

static void loadSettings() {
  prefs.begin("dashan", true);
  wifiSsid = prefs.getString("ssid", "");
  wifiPassword = prefs.getString("pass", "");
  backendUrl = prefs.getString("backend", "");
  deviceToken = prefs.getString("token", "");
  prefs.end();
  backendUrl.trim();
  while (backendUrl.endsWith("/")) backendUrl.remove(backendUrl.length() - 1);
  uint64_t chip = ESP.getEfuseMac();
  char suffix[13];
  snprintf(suffix, sizeof(suffix), "%012llX", (unsigned long long)chip);
  deviceId = String("dashan-") + suffix;
}

static bool initCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0; c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = CAM_D0; c.pin_d1 = CAM_D1; c.pin_d2 = CAM_D2; c.pin_d3 = CAM_D3;
  c.pin_d4 = CAM_D4; c.pin_d5 = CAM_D5; c.pin_d6 = CAM_D6; c.pin_d7 = CAM_D7;
  c.pin_xclk = CAM_XCLK; c.pin_pclk = CAM_PCLK; c.pin_vsync = CAM_VSYNC;
  c.pin_href = CAM_HREF;
  // Reuse I2C0 already initialized for ES8311 instead of creating a second bus.
  c.pin_sccb_sda = -1; c.pin_sccb_scl = -1; c.sccb_i2c_port = 0;
  c.pin_pwdn = -1; c.pin_reset = -1; c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = psramFound() ? FRAMESIZE_UXGA : FRAMESIZE_SVGA;
  c.jpeg_quality = psramFound() ? 12 : 16;
  c.fb_count = psramFound() ? 2 : 1;
  c.grab_mode = CAMERA_GRAB_LATEST;
  esp_err_t result = esp_camera_init(&c);
  Serial.printf("camera init: 0x%x\n", result);
  return result == ESP_OK;
}

static String setupPage(const String &message = "") {
  int found = WiFi.scanNetworks();
  String options;
  for (int i = 0; i < found; i++) {
    options += F("<option value=\""); options += htmlEscape(WiFi.SSID(i)); options += F("\">");
    options += htmlEscape(WiFi.SSID(i)); options += F(" ("); options += WiFi.RSSI(i); options += F(" dBm)</option>");
  }
  return String(F("<!doctype html><html lang=zh-CN><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
    "<title>DASHAN 设备配网</title><style>body{margin:0;background:#f3f1eb;color:#20201d;font:16px system-ui}main{max-width:560px;margin:auto;padding:34px 22px}"
    "h1{font-family:Georgia,serif;letter-spacing:.12em}section{background:#fff;padding:22px;border-radius:14px;box-shadow:0 8px 30px #0001}label{display:block;margin:18px 0 7px}"
    "input,select,button{box-sizing:border-box;width:100%;padding:13px;border:1px solid #cbc8bf;border-radius:8px;font:inherit}button{margin-top:24px;background:#20201d;color:#fff}.tip{color:#777;font-size:14px}</style>"
    "<main><h1>DASHAN</h1><p>诗歌相机设备配网</p><section>")) +
    (message.length() ? String(F("<p>")) + htmlEscape(message) + F("</p>") : "") +
    F("<form method=post action=/save><label>Wi-Fi</label><select name=ssid>") + options +
    F("</select><label>Wi-Fi 密码</label><input type=password name=pass autocomplete=current-password>"
      "<label>导演台后端地址</label><input name=backend placeholder='https://example.com/dashan-api' required>"
      "<label>设备令牌</label><input type=password name=token required><button>保存并重启</button></form>"
      "<p class=tip>AI 的 API Key 只在服务器导演台中保存，不会写入相机。</p></section></main></html>");
}

static void startSetupMode() {
  setupMode = true;
  detectiveDisplaySetState(DetectiveScreenState::Setup);
  WiFi.mode(WIFI_AP_STA);
  String ap = String("DASHAN-CAMERA-") + deviceId.substring(deviceId.length() - 4);
  WiFi.setSleep(false);
  bool apStarted = WiFi.softAP(ap.c_str(), nullptr, 1, false, 4);
  dnsServer.start(53, "*", WiFi.softAPIP());
  setupServer.on("/", HTTP_GET, [] { setupServer.send(200, "text/html; charset=utf-8", setupPage()); });
  setupServer.on("/save", HTTP_POST, [] {
    String ssid = setupServer.arg("ssid"), pass = setupServer.arg("pass");
    String backend = setupServer.arg("backend"), token = setupServer.arg("token");
    backend.trim(); token.trim();
    if (!ssid.length() || !backend.startsWith("http") || !token.length()) {
      setupServer.send(400, "text/html; charset=utf-8", setupPage("请填写完整信息。")); return;
    }
    while (backend.endsWith("/")) backend.remove(backend.length() - 1);
    prefs.begin("dashan", false);
    prefs.putString("ssid", ssid); prefs.putString("pass", pass);
    prefs.putString("backend", backend); prefs.putString("token", token);
    prefs.end();
    setupServer.send(200, "text/html; charset=utf-8", setupPage("已保存，相机正在重启。"));
    delay(800); ESP.restart();
  });
  setupServer.onNotFound([] { setupServer.sendHeader("Location", "/", true); setupServer.send(302, "text/plain", ""); });
  setupServer.begin();
  Serial.printf("setup AP: %s started=%s clients=%d http://%s/\n", ap.c_str(), apStarted ? "yes" : "no", WiFi.softAPgetStationNum(), WiFi.softAPIP().toString().c_str());
}

static bool connectWifi() {
  if (!wifiSsid.length()) return false;
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(wifiSsid.c_str(), wifiPassword.c_str());
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("wifi: %s\n", WiFi.localIP().toString().c_str());
    return true;
  }
  return false;
}

static int postJson(const String &path, const String &body, String *response = nullptr) {
  if (WiFi.status() != WL_CONNECTED || !backendUrl.length()) return -1;
  HTTPClient http;
  http.begin(backendUrl + path);
  http.setTimeout(15000);
  if(path=="/api/device/heartbeat"){
    http.setConnectTimeout(600);
    http.setTimeout(600);
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Dashan-Token", deviceToken);
  http.addHeader("X-Dashan-Device", deviceId);
  int code = http.POST((uint8_t *)body.c_str(), body.length());
  Serial.printf("POST %s%s -> %d\n", backendUrl.c_str(), path.c_str(), code);
  if (response && code > 0) *response = http.getString();
  http.end();
  return code;
}

static bool writeMcpRegister(uint8_t reg, uint8_t value) {
  BoardI2cGuard lock;
  Wire.beginTransmission(SHUTTER_MCP_ADDR);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

static bool readMcpRegister(uint8_t reg, uint8_t &value) {
  BoardI2cGuard lock;
  Wire.beginTransmission(SHUTTER_MCP_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)SHUTTER_MCP_ADDR, 1) != 1) return false;
  value = Wire.read();
  return true;
}

static bool beginPhysicalShutter() {
  // MCP23017 default BANK=0: IODIRB=0x01, GPPUB=0x0D, GPIOB=0x13.
  // Keep all port-B pins as inputs and enable the internal pull-up only on PB0.
  const bool ok = writeMcpRegister(0x01, 0xFF) && writeMcpRegister(0x0D, 0x01);
  uint8_t gpio = 0xFF;
  shutterReady = ok && readMcpRegister(SHUTTER_GPIOB_REG, gpio);
  shutterRawPressed = shutterStablePressed = shutterReady && !(gpio & 0x01);
  shutterArmed = !shutterStablePressed;
  shutterChangedAt = millis();
  Serial.printf("shutter: %s initial=%s\n", shutterReady ? "ready" : "init_failed",
                shutterStablePressed ? "pressed" : "released");
  return shutterReady;
}

static void toggleStandby() {
  if(standbyActive){
    Serial.println("standby: waking by restart");
    Serial.flush();
    ESP.restart();
    return;
  }
  if(printerBusy || investigationActive || voiceAudioPlaying ||
     caseNarrationState==1 || caseNarrationState==2 ||
     reportAnnouncementState==1 || reportAnnouncementState==2 || voiceTestEnd){
    Serial.println("standby: busy; finish current case first");
    return;
  }
  standbyDisplayDone=false;
  standbyVoiceDone=voiceTaskHandle==nullptr;
  standbyRequested=true;
  if(!displayTaskHandle)standbyDisplayDone=detectiveDisplayStandby();
  const uint32_t started=millis();
  while((!standbyDisplayDone || !standbyVoiceDone) && millis()-started<2000)delay(10);
  if(!standbyDisplayDone || !standbyVoiceDone){
    Serial.println("standby: peripheral stop failed; restarting to recover");
    ESP.restart();
    return;
  }
  {
    CameraGuard guard;
    if(cameraReady)esp_camera_deinit();
    cameraReady=false;
  }
  WiFi.disconnect(false);
  WiFi.mode(WIFI_OFF);
  standbyActive=true;
  Serial.println("standby: entered; hold shutter 2s to wake");
}

static void queueShutterEvent(uint8_t event){
  // Never defer an in-case press until after the case has completed.
  if(!standbyActive && (printerBusy || investigationActive || voiceAudioPlaying ||
     caseNarrationState==1 || caseNarrationState==2 ||
     reportAnnouncementState==1 || reportAnnouncementState==2 || voiceTestEnd)){
    Serial.println("shutter: busy; press again after case finishes");
    return;
  }
  if(shutterEvents && xQueueSend(shutterEvents,&event,0)!=pdTRUE)
    Serial.println("shutter: event queue full");
}
static void servicePhysicalShutter() {
  static uint32_t lastRetry = 0;
  if (!shutterReady) {
    if (millis() - lastRetry >= 2000) {
      lastRetry = millis();
      beginPhysicalShutter();
    }
    return;
  }
  uint8_t gpio = 0xFF;
  if (!readMcpRegister(SHUTTER_GPIOB_REG, gpio)) {
    shutterReady = false;
    Serial.println(F("shutter: I2C read failed; retrying initialization"));
    return;
  }
  const bool pressed = !(gpio & 0x01);
  const uint32_t now = millis();
  if (pressed != shutterRawPressed) {
    shutterRawPressed = pressed;
    shutterChangedAt = now;
  }
  if(pressed && shutterStablePressed && shutterArmed && !shutterLongHandled &&
     now-shutterPressedAt>=2000){
    shutterLongHandled=true;
    Serial.println("shutter: long_press 2s");
    queueShutterEvent(2);
    return;
  }
  if (pressed == shutterStablePressed || now - shutterChangedAt < SHUTTER_DEBOUNCE_MS) return;
  shutterStablePressed = pressed;
  if (pressed) {
    Serial.println("shutter: pressed");
    shutterPressedAt=now;
    shutterLongHandled=false;
    return;
  }
  if(shutterArmed && !shutterLongHandled && now-shutterPressedAt>=2000){
    shutterLongHandled=true;
    Serial.println("shutter: long_press released");
    queueShutterEvent(2);
  }
  const bool shortPress=shutterArmed && !shutterLongHandled;
  shutterArmed=true;
  if(!shortPress || standbyActive || setupMode)return;
  Serial.printf("shutter: short_press duration=%u ms\n",now-shutterPressedAt);
  queueShutterEvent(1);
}

static void shutterTask(void *){
  TickType_t lastWake=xTaskGetTickCount();
  for(;;){
    if(shutterSamplingEnabled)servicePhysicalShutter();
    vTaskDelayUntil(&lastWake,pdMS_TO_TICKS(5));
  }
}

static void processShutterEvent(){
  uint8_t event=0;
  if(!shutterEvents || xQueueReceive(shutterEvents,&event,0)!=pdTRUE)return;
  if(event==2){toggleStandby();return;}
  if(standbyActive || setupMode)return;
  if (!cameraReady || printerBusy || investigationActive || WiFi.status() != WL_CONNECTED) {
    Serial.println(F("shutter: ignored_busy_or_offline"));
    return;
  }
  char localId[33];
  snprintf(localId, sizeof(localId), "%08lx%08lx%08lx%08lx",
           (unsigned long)(ESP.getEfuseMac() >> 32),
           (unsigned long)ESP.getEfuseMac(),
           (unsigned long)millis(), (unsigned long)esp_random());
  Serial.printf("shutter: capture_start id=%s\n", localId);
  executeJob(String(F("{\"type\":\"photo_capture\",\"job_id\":\"")) + localId + F("\"}"));
}

static void sendHeartbeat() {
  String body = String(F("{\"device_id\":\"")) + jsonEscape(deviceId) +
    F("\",\"ip\":\"") + WiFi.localIP().toString() +
    F("\",\"rssi\":") + WiFi.RSSI() +
    F(",\"firmware\":\"director-0.5.4-result\",\"narration\":\"mp3-result-v4\",\"camera\":\"") + (cameraReady ? "ready" : "not_ready") +
    F("\",\"printer\":\"connected\",\"voice\":\"") + (voiceReady ? "ready" : "not_ready") +
    F("\",\"camera_revision\":") + cameraRevision + F("}");
  String response;
  if (postJson("/api/device/heartbeat", body, &response) == 200) {
    detectiveDisplaySetConnected(true);
    cameraSettingsJson = response;
    applyCameraSettings(response);
  }
}

static void completeJob(const String &jobId, const String &status, const String &detail) {
  String body = String(F("{\"status\":\"")) + jsonEscape(status) + F("\",\"detail\":\"") + jsonEscape(detail) + F("\"}");
  postJson(String("/api/device/jobs/") + jobId + "/complete", body);
}

static bool printRasterJob(const String &jobId, String &detail) {
  HTTPClient http;
  http.begin(backendUrl + "/api/device/jobs/" + jobId + "/print-data");
  http.setTimeout(120000);
  http.addHeader("X-Dashan-Token", deviceToken);
  http.addHeader("X-Dashan-Device", deviceId);
  int code = http.GET();
  if (code != 200) {
    detail = String("print_data_http_") + code;
    http.end();
    return false;
  }
  int remaining = http.getSize();
  if (remaining <= 10 || remaining > 120000) {
    detail = "invalid_print_data_size";
    http.end();
    return false;
  }
  WiFiClient *stream = http.getStreamPtr();
  uint8_t buffer[1152];
  int sent = 0;
  uint32_t lastData = millis();
  // Track complete GS v 0 packets and pause at raster boundaries, not
  // arbitrary TCP chunks. This also supports legacy single-image jobs.
  uint8_t header[8] = {};
  uint8_t headerCount = 0;
  uint32_t rasterRemaining = 0;
  while (http.connected() && remaining > 0) {
    size_t available = stream->available();
    if (!available) {
      if (millis() - lastData > 15000) break;
      delay(2); continue;
    }
    size_t take = min(available, min(sizeof(buffer), (size_t)remaining));
    if (rasterRemaining) take = min(take, (size_t)rasterRemaining);
    else take = 1;
    int got = stream->readBytes(buffer, take);
    if (got <= 0) break;
    lastData = millis();
    printer.write(buffer, got);
    sent += got;
    remaining -= got;
    if (rasterRemaining) {
      rasterRemaining -= got;
      printer.flush();
      if (!rasterRemaining) delay(100);
    } else {
      uint8_t b = buffer[0];
      if (headerCount || b == 0x1D) {
        header[headerCount++] = b;
        if ((headerCount == 2 && b != 0x76) || (headerCount == 3 && b != 0x30)) headerCount = 0;
        if (headerCount == 8) {
          rasterRemaining = (uint32_t)(header[4] | (header[5] << 8)) * (header[6] | (header[7] << 8));
          headerCount = 0;
        }
      }
    }
  }
  printer.flush();
  http.end();
  detail = String("raster_bytes_") + sent;
  return remaining == 0;
}

static void printWorker(void *) {
  const String jobId = activePrintJob;
  uint32_t waitStarted = millis();
  while (synchronizedPrint && reportAnnouncementState != 3 && reportAnnouncementState != 4 && millis() - waitStarted < 30000) delay(10);
  String detail;
  bool ok = printRasterJob(jobId, detail);
  completeJob(jobId, ok ? "completed" : "failed", detail);
  Serial.printf("print: %s %s\n", ok ? "sent" : "failed", detail.c_str());
  printerBusy = false;
  vTaskDelete(nullptr);
}

static void executeJob(const String &json) {
  String jobId = jsonString(json, "job_id");
  String type = jsonString(json, "type");
  if (!jobId.length()) return;
  if (type == "preview_capture") {
    CameraGuard guard;
    if (!cameraReady) return;
    sensor_t *sensor = esp_camera_sensor_get();
    if (!sensor) return;
    sensor->set_framesize(sensor, FRAMESIZE_QVGA);
    sensor->set_quality(sensor, 24);
    delay(45);
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) {
      HTTPClient http;
      http.begin(backendUrl + "/api/camera-preview");
      http.setTimeout(15000);
      http.addHeader("Content-Type", "image/jpeg");
      http.addHeader("X-Dashan-Token", deviceToken);
      http.addHeader("X-Dashan-Device", deviceId);
      int code = http.POST(fb->buf, fb->len);
      Serial.printf("live preview -> %d bytes=%u\n", code, (unsigned)fb->len);
      http.end();
      esp_camera_fb_return(fb);
    }
    cameraRevision = 0;
    if (cameraSettingsJson.length()) applyCameraSettings(cameraSettingsJson);
    return;
  }
  if (type == "capture" || type == "photo_capture") {
    detectiveDisplaySetState(DetectiveScreenState::Capturing);
    CameraGuard guard;
    if (!cameraReady) {
      finishInvestigationVoices(VoiceStage::Error);
      completeJob(jobId, "failed", "camera_not_ready");
      return;
    }
    if(cameraPreviewMode){
      cameraRevision=0;
      if(cameraSettingsJson.length())applyCameraSettings(cameraSettingsJson);
      else {
        sensor_t *sensor=esp_camera_sensor_get();
        sensor->set_framesize(sensor,psramFound()?FRAMESIZE_UXGA:FRAMESIZE_SVGA);
        sensor->set_quality(sensor,12);cameraPreviewMode=false;
      }
      for(int n=0;n<2;n++){camera_fb_t *old=esp_camera_fb_get();if(old)esp_camera_fb_return(old);}
    }
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      finishInvestigationVoices(VoiceStage::Error);
      completeJob(jobId, "failed", "capture_failed");
      return;
    }
    // Group one acknowledges a captured frame, before any upload wait.
    requestVoice(VoiceStage::Capture, true);
    beginInvestigationVoices();
    HTTPClient http;
    http.begin(backendUrl + "/api/camera?job_id=" + jobId);
    http.setTimeout(60000);
    http.addHeader("Content-Type", "image/jpeg");
    http.addHeader("X-Dashan-Token", deviceToken);
    http.addHeader("X-Dashan-Device", deviceId);
    int code = http.POST(fb->buf, fb->len);
    String result = code > 0 ? http.getString() : String("http_") + code;
    http.end(); esp_camera_fb_return(fb);
    bool ok = code >= 200 && code < 300;
    completeJob(jobId, ok ? "completed" : "failed", result.substring(0, 180));
    if (!ok) finishInvestigationVoices(VoiceStage::Error);
    detectiveDisplaySetState(ok ? DetectiveScreenState::Deducing : DetectiveScreenState::Error);
    return;
  }
  if (type == "print" || type == "manual_print" || type == "raster_print") {
    if (printerBusy) { completeJob(jobId, "failed", "printer_busy"); return; }
    // A print job means the case text is ready. Stop scheduling thought
    // lines immediately, independently of TTS generation/download timing.
    investigationActive = false;
    reportAnnouncementSawRunning = false;
    reportAnnouncementState = 1;
    requestVoice(VoiceStage::PrintStart, false);
    String audioJobId = jsonString(json, "audio_job_id");
    String audioDetail;
    // Printing must always wait for the fixed report announcement.  This is
    // independent of whether the separately generated case narration is
    // already ready. Start the print worker before waiting on that download:
    // if narration is ready first, both start together after the announcement;
    // if narration is late, printing starts immediately after the announcement.
    synchronizedPrint = true;
    caseNarrationState = 0;
    detectiveDisplaySetState(DetectiveScreenState::Printing);
    activePrintJob = jobId;
    printerBusy = true;
    if (xTaskCreatePinnedToCore(printWorker, "printer", 8192, nullptr, 1, nullptr, 1) != pdPASS) {
      printerBusy = false;
      completeJob(jobId, "failed", "print_worker_failed");
    }
    if (audioJobId.length()) {
      bool audioOk = downloadCaseNarration(audioJobId, audioDetail);
      if (audioOk) audioOk = playCaseNarration(audioJobId, audioDetail);
      completeJob(audioJobId, audioOk ? "completed" : "failed", audioDetail);
    }
    return;
  }
  if (type == "case_audio") {
    String detail;
    bool ok = downloadCaseNarration(jobId, detail);
    if (ok) ok = playCaseNarration(jobId, detail);
    completeJob(jobId, ok ? "completed" : "failed", detail);
    return;
  }
  finishInvestigationVoices(VoiceStage::Error);
  completeJob(jobId, "failed", "unknown_job_type");
}

static void pollJob() {
  HTTPClient http;
  http.begin(backendUrl + "/api/device/jobs/next");
  http.setConnectTimeout(600);
  http.setTimeout(600);
  http.addHeader("X-Dashan-Token", deviceToken);
  http.addHeader("X-Dashan-Device", deviceId);
  int code = http.GET();
  if (code == 200) executeJob(http.getString());
  http.end();
}

void setup() {
  Serial.begin(115200);
  printer.begin(PRINTER_BAUD, SERIAL_8N1, PRINTER_RX, PRINTER_TX);
  pinMode(SETUP_BUTTON, INPUT_PULLUP);
  // The LCD reset/backlight lines are controlled by the on-board CH32V003
  // expander at 0x24.  Bring up the shared I2C bus before display init;
  // previously it was only started later by the audio codec, leaving a newly
  // connected LCD permanently dark during boot.
  Wire.begin(CAM_SDA, CAM_SCL, 400000);
  boardI2cMutex=xSemaphoreCreateRecursiveMutex();
  cameraMutex=xSemaphoreCreateRecursiveMutex();
  const bool displayReady = detectiveDisplayBegin();
  Serial.printf("display: %s\n", displayReady ? "ready" : "init_failed");
  beginPhysicalShutter();
  shutterEvents=xQueueCreate(4,sizeof(uint8_t));
  detectiveDisplaySetState(DetectiveScreenState::Boot);
  if(cameraMutex && displayReady)
    xTaskCreatePinnedToCore(displayTask,"display",8192,nullptr,1,&displayTaskHandle,1);
  loadSettings();
  Serial.printf("saved ssid: [%s]\n", wifiSsid.c_str());
  Serial.printf("saved backend: [%s], token length: %u\n", backendUrl.c_str(), (unsigned)deviceToken.length());
  bool forceSetup = digitalRead(SETUP_BUTTON) == LOW;
  // A remembered Wi-Fi alone is not a complete configuration.  Older test
  // builds may have left only the SSID in NVS, which would suppress the setup
  // hotspot even though the camera cannot reach the director backend.
  bool backendIsSetupPortal = backendUrl == "http://192.168.4.1" || backendUrl.startsWith("http://192.168.4.1/");
  bool incompleteSettings = !wifiSsid.length() || !backendUrl.length() || !deviceToken.length() || backendIsSetupPortal;
  if (forceSetup || incompleteSettings || !connectWifi()) startSetupMode();
  else {
    startVoiceSystem();
    cameraReady = initCamera();
    detectiveDisplaySetState(cameraReady ? DetectiveScreenState::Ready : DetectiveScreenState::Error);
  }
}

void loop() {
  static bool samplerStarted=false;
  if(!samplerStarted){
    samplerStarted=true;
    xTaskCreatePinnedToCore(shutterTask,"shutter",4096,nullptr,2,&shutterTaskHandle,1);
    Serial.printf("shutter: dedicated sampler=%s debounce=20ms\n",shutterTaskHandle?"ready":"fallback");
  }
  shutterSamplingEnabled=true;
  if(!shutterTaskHandle)servicePhysicalShutter();
  processShutterEvent();
  if(standbyActive){
    // USB maintenance wake, also used to verify standby without a key press.
    while(Serial.available())if(Serial.read()=='R')toggleStandby();
    delay(20);return;
  }
  if (voiceTestEnd && (int32_t)(millis() - voiceTestEnd) >= 0) {
    voiceTestEnd = 0;
    investigationActive = false;
    requestVoice(VoiceStage::PrintStart, false);
    Serial.println("voice: sequence test ending");
    if (voiceTestNarration) {
      voiceTestNarration = false;
      String detail;
      bool ok = playCaseNarration("local-sequence-test", detail);
      Serial.printf("voice: full test %s %s\n", ok ? "complete" : "failed", detail.c_str());
    }
  }
  detectiveDisplayService(voiceAudioPlaying);
  // USB serial voice self-test: send 1..5 for capture/wait/long-wait/
  // printing/error.  This remains available for servicing the assembled unit.
  while (Serial.available()) {
    const char command = Serial.read();
    if(command=='S'){toggleStandby();if(standbyActive)return;}
    if (command == 'l') detectiveDisplayRequestSelfTest();
    if (command == 'u') {
      // Maintenance upload: fixed report voice only, no arbitrary file path.
      if (printerBusy || investigationActive || voiceAudioPlaying || caseNarrationState == 1 || caseNarrationState == 2) {
        Serial.println("voice: upload_busy");
        continue;
      }
      Serial.setTimeout(15000);
      Serial.println("voice: upload_ready");
      uint8_t header[4];
      bool ok = Serial.readBytes(header, 4) == 4;
      uint32_t length = ok ? (uint32_t)header[0] | ((uint32_t)header[1]<<8) | ((uint32_t)header[2]<<16) | ((uint32_t)header[3]<<24) : 0;
      ok = ok && length >= 1024 && length <= 256000;
      File output;
      if (ok) { output = FFat.open("/voice/report.tmp", FILE_WRITE); ok = bool(output); }
      uint8_t block[512];
      uint32_t received = 0;
      while (ok && received < length) {
        size_t take = min((uint32_t)sizeof(block), length - received);
        size_t got = Serial.readBytes(block, take);
        ok = got == take && output.write(block, got) == got;
        received += got;
      }
      if (output) output.close();
      if (ok) {
        FFat.remove("/voice/report.previous.mp3");
        if (FFat.exists("/voice/report.mp3")) ok = FFat.rename("/voice/report.mp3", "/voice/report.previous.mp3");
        if (ok) ok = FFat.rename("/voice/report.tmp", "/voice/report.mp3");
      }
      if (!ok) {
        FFat.remove("/voice/report.tmp");
        if (!FFat.exists("/voice/report.mp3") && FFat.exists("/voice/report.previous.mp3")) FFat.rename("/voice/report.previous.mp3", "/voice/report.mp3");
      }
      Serial.printf("voice: upload_%s bytes=%u\n", ok ? "complete" : "failed", received);
      Serial.setTimeout(1000);
    }
    if (command == 'w' || command == 'v') {
      voiceTestNarration = command == 'v';
      requestVoice(VoiceStage::Capture, true);
      beginInvestigationVoices();
      voiceTestEnd = millis() + 20000;
      Serial.println("voice: sequence test started (20s, no camera or printer)");
    }
    if (command == '?') {
      BoardI2cGuard lock;
      Serial.print("shutter: I2C address scan:");
      for(uint8_t address=0x20;address<=0x27;address++){
        Wire.beginTransmission(address);
        if(Wire.endTransmission()==0)Serial.printf(" 0x%02x",address);
      }
      Serial.println();
      uint8_t shutterGpio = 0xFF;
      bool shutterRead = readMcpRegister(SHUTTER_GPIOB_REG, shutterGpio);
      Serial.printf("shutter: ready=%d read=%d address=0x%02x GPIOB=0x%02x PB0=%s armed=%d\n",
                    shutterReady, shutterRead, SHUTTER_MCP_ADDR, shutterGpio,
                    (shutterGpio & 1) ? "released" : "pressed", shutterArmed);
      Wire.beginTransmission(0x18);
      const int codecI2c = Wire.endTransmission();
      Wire.beginTransmission(0x24);
      const int ampI2c = Wire.endTransmission();
      Serial.printf("voice: status fs=%d codec=%d amp=%d queue=%d i2c18=%d i2c24=%d file01=%d used=%u total=%u\n",
                    voiceFsReady, voiceCodecReady, voiceAmpReady, voiceQueue != nullptr,
                    codecI2c, ampI2c,
                    voiceFsReady && FFat.exists("/voice/01_shutter.mp3"),
                    voiceFsReady ? (unsigned)FFat.usedBytes() : 0,
                    voiceFsReady ? (unsigned)FFat.totalBytes() : 0);
    }
    if (command >= '1' && command <= '5') {
      const VoiceStage stages[] = {VoiceStage::Capture, VoiceStage::Waiting,
                                   VoiceStage::LongWait, VoiceStage::PrintStart,
                                   VoiceStage::Error};
      Serial.printf("voice: manual test stage %c\n", command);
      requestVoice(stages[command - '1'], true);
    }
  }
  if (setupMode) {
    dnsServer.processNextRequest(); setupServer.handleClient();
    uint32_t now = millis();
    if (now - lastSetupLog >= 2000) {
      lastSetupLog = now;
      Serial.printf("AP alive: %s clients=%d ip=%s\n", WiFi.softAPSSID().c_str(), WiFi.softAPgetStationNum(), WiFi.softAPIP().toString().c_str());
    }
    delay(2); return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    detectiveDisplaySetConnected(false);
    static uint32_t lastReconnect=0;
    if(millis()-lastReconnect>=10000){lastReconnect=millis();WiFi.reconnect();}
    delay(10);return;
  }
  uint32_t now = millis();
  if(cameraReady && !investigationActive && !voiceAudioPlaying &&
     (caseNarrationState==3 || caseNarrationState==4) &&
     (reportAnnouncementState==3 || reportAnnouncementState==4)){
    detectiveDisplaySetState(DetectiveScreenState::Ready);
  }
  serviceInvestigationVoices();
  if (now - lastHeartbeat >= 15000) { lastHeartbeat = now; sendHeartbeat(); }
  if (now - lastPoll >= (investigationActive ? 500UL : 1500UL)) { lastPoll = now; pollJob(); }
  delay(5);
}
