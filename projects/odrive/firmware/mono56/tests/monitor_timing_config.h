#pragma once
#include "timing_monitor.hpp"
namespace odrive::mono56 {
// Synthetic inhibited-timing fixture; not qualified electrical/latency bounds.
inline constexpr TimingMonitorConfig monitor_timing_config{
    {3500, 200, 2500, 100, 500, 2000, 2000}, 1000, 1000, 30, 32, 1200, 1500, 1900};
}
