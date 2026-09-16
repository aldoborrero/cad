#pragma once
#include "drv8353.hpp"
#include <cstdint>

namespace odrive::mono56 {
struct DriverWakeConfig {
    std::uint32_t (*clock_us)();
    void *bus_context;
    // Must check freshness and retained bus faults, not just a cached voltage.
    bool (*bus_permitted)(void *);
    // Explicit qualification parameters, not production defaults. A 1 us
    // quantized clock requires >=1001 us for the datasheet's 1 ms sleep/wake.
    std::uint32_t sleep_us, wake_us, feedback_timeout_us, max_service_gap_us;
};
enum class DriverWakeState {
    idle,
    waiting_off,
    sleeping,
    waiting_on,
    waking,
    awake,
    fault,
    timing
};
struct DriverTimingPermission {
    void *context;
    // IRQ-safe freshness/fault check with NO heartbeat renewal, SPI or waiting.
    // This is distinct from startup callbacks that may feed foreground leases.
    bool (*permitted)(void *);
};
enum class DriverWakeError {
    none,
    invalid_config,
    invalid_state,
    gpio_owner,
    clock_error,
    service_late,
    bus_permission,
    gpio_configuration,
    outputs_not_quiet,
    brake_permission,
    enable_history,
    request_mismatch,
    feedback_timeout,
    nfault,
    register_session
};

// Single serialized foreground owner; no waiting loops, automatic restart or PWM
// release. The board must schedule update even when no SPI calls are needed.
// Qualified awake is sufficient only for register setup with all PWM inputs LOW.
// Do not use this startup owner unchanged for a running current controller.
class DriverWake {
  public:
    DriverWake() = default;
    DriverWake(const DriverWake &) = delete;
    DriverWake &operator=(const DriverWake &) = delete;
    [[nodiscard]] bool begin(const DriverWakeConfig &config);
    DriverWakeState update();
    // Foreground transition after idle capture release and verified normal CSA
    // restoration. Keeps ENABLE/history and verifies the COASTed driver over SPI.
    // Allows internal TIM1/ADC operation with all PWM GPIOs LOW and CCER/MOE/AOE
    // clear. Does not authorize switching or transfer/validate a current zero.
    [[nodiscard]] bool begin_timing(Drv8353 &, const DriverTimingPermission &);
    // IRQ-safe guard for the timing/capture owner. Checks the foreground lease
    // without renewing it. update()/SPI callbacks remain foreground operations.
    [[nodiscard]] bool timing_permitted();
    // Explicit teardown discards this owner's diagnostics; the Drv8353 session
    // must also be explicitly reset before new configuration. Never raises EN.
    void reset();
    [[nodiscard]] bool permitted();
    // Supply the SPI3 adapter (or a simulated exchange in tests). Its context
    // receives this owner; the production SPI3 adapter deliberately ignores it.
    [[nodiscard]] constexpr Drv8353Io io(bool (*exchange)(void *, std::uint16_t, std::uint16_t *)) {
        return {this, exchange, awake_callback, quiet_callback, nfault_callback, inhibit_callback};
    }
    [[nodiscard]] DriverWakeState state() const { return state_; }
    [[nodiscard]] DriverWakeError error() const { return error_; }

  private:
    bool fail(DriverWakeError error);
    bool check_timing(bool renew);
    static bool awake_callback(void *context);
    static bool quiet_callback(void *context);
    static bool nfault_callback(void *context);
    static void inhibit_callback(void *context);
    DriverWakeConfig config_{};
    DriverTimingPermission timing_{};
    volatile DriverWakeState state_ = DriverWakeState::idle;
    volatile DriverWakeError error_ = DriverWakeError::none;
    std::uint32_t phase_at_ = 0, last_observed_ = 0;
};
} // namespace odrive::mono56
