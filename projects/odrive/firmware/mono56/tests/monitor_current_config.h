#pragma once
#include "current_monitor.hpp"
namespace odrive::mono56 {
// Synthetic integration fixture. Not qualified electrical/analog settings.
// Mutable only in host tests to exercise invalid and tighter timing requests.
inline CurrentMonitorConfig monitor_current_config{
    {0.001f, 0.001f, 20, 1, 1, 250, 25, 250, 1000000, 3.0f, 3.6f, 0.30f, 40.0f, 16.0f, 0.05f},
    {8, 100, 6900, 30000, 4},
    1000,
    10};
} // namespace odrive::mono56
