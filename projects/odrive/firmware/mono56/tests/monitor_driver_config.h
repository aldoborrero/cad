#pragma once
// Host-only encoding/timing fixture. NOT a qualified 56 V gate/current profile.
#include "driver_monitor.hpp"
namespace odrive::mono56 {
inline constexpr DriverMonitorConfig monitor_driver_config{
    {150, 300, 150, 300, 2000, 200, 200, 2, 20, 250}, 2000, 2000, 250, 250, 200, 1000, 1000};
}
