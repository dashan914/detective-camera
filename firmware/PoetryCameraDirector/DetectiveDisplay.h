#pragma once

#include <Arduino.h>
extern SemaphoreHandle_t boardI2cMutex;
struct BoardI2cGuard {
  BoardI2cGuard(){if(boardI2cMutex)xSemaphoreTakeRecursive(boardI2cMutex,portMAX_DELAY);}
  ~BoardI2cGuard(){if(boardI2cMutex)xSemaphoreGiveRecursive(boardI2cMutex);}
};

enum class DetectiveScreenState : uint8_t {
  Boot,
  Setup,
  Ready,
  Capturing,
  Deducing,
  Printing,
  Error
};

bool detectiveDisplayBegin();
bool detectiveDisplayStandby();
void detectiveDisplayRequestSelfTest();
void detectiveDisplaySetState(DetectiveScreenState state, const char *detail = nullptr);
void detectiveDisplaySetConnected(bool connected);
void detectiveDisplayService(bool voicePlaying);
bool detectiveDisplayReady();
bool detectiveDisplayWantsPreview();
bool detectiveDisplayPreview(const uint8_t *jpeg, size_t length, int width, int height);
