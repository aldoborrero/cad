#pragma once
#include <array>
#include <cstdint>

namespace odrive::mono56 {

// Exact choices from TI SLVSDY6A tables 15-18. No production defaults or rounding.
struct Drv8353Config {
    std::uint16_t hs_source_ma, hs_sink_ma, ls_source_ma, ls_sink_ma;
    std::uint16_t drive_time_ns, dead_time_ns, vds_trip_mv;
    std::uint8_t ocp_deglitch_us, csa_gain;
    std::uint16_t sense_trip_mv;
};
struct Drv8353Registers {
    // Addresses 2..7. Includes six-input mode, COAST, all-bridge latched OCP,
    // OTW reporting, enabled protections, bidirectional shunt sensing, manual CAL.
    std::array<std::uint16_t, 6> values{};
};
[[nodiscard]] bool make_drv8353_registers(const Drv8353Config &config, Drv8353Registers &registers);

struct Drv8353Faults {
    std::uint16_t status1 = 0, status2 = 0;
    bool valid = false;
    [[nodiscard]] bool any() const { return valid && (status1 || status2); }
    // Preserve every bit of BOTH status registers, unlike the old DRV8301 map.
    [[nodiscard]] std::uint32_t packed() const {
        return status1 | (static_cast<std::uint32_t>(status2) << 16);
    }
};

struct Drv8353Io {
    void *context;
    // Exactly one 16-clock, MSB-first, SPI mode-1 transaction, with bounded
    // timeout, >=400 ns nCS-high spacing and specified setup/hold timing.
    bool (*exchange)(void *, std::uint16_t tx, std::uint16_t *rx);
    // Qualified continuous ENABLE/wake history, fresh bus/brake/rail permission.
    // An observed loss must stay false until the board's explicit restart.
    bool (*awake_and_permitted)(void *);
    // All six PWM inputs held LOW and PWM timer unable to start switching.
    bool (*outputs_quiet)(void *);
    bool (*nfault_high)(void *);
    // Immediate PWM/ENABLE inhibition, without SPI, sleep or fault clear.
    void (*inhibit)(void *);
};

enum class Drv8353Error {
    none,
    invalid_io,
    invalid_config,
    invalid_state,
    permission_lost,
    outputs_not_quiet,
    transport,
    hardware_fault,
    readback_mismatch,
    reserved_bits
};

// Single serialized owner. This class NEVER raises ENABLE or starts a PWM timer.
// The board owns safe wake timing, interlock edges, current calibration and arm.
class Drv8353 {
  public:
    explicit constexpr Drv8353(Drv8353Io io) : io_(io) {}
    Drv8353(const Drv8353 &) = delete;
    Drv8353 &operator=(const Drv8353 &) = delete;
    // Requires a qualified full sleep/reset then wake with all inputs LOW.
    // LOW inputs imply all gates off only in the known reset six-PWM mode;
    // a prior unknown 3-PWM mode cannot be treated as a safe wake condition.
    // Returns configured but COASTed; is not permission to move a motor.
    [[nodiscard]] bool configure_coasted(const Drv8353Config &config);
    // Explicit B/C manual input-short transitions. Require configured COAST,
    // all PWM inputs LOW, and uninterrupted permission. Unlock/change/relock
    // with full readback on both sides. Do not collect samples until begin
    // succeeds and analog/ADC settling has elapsed. End does not release COAST.
    [[nodiscard]] bool begin_current_calibration();
    [[nodiscard]] bool end_current_calibration();
    // Explicit arm-owner step. Validates all configuration/status first, clears
    // COAST while inputs remain LOW, and verifies that write. No timer enable.
    [[nodiscard]] bool release_coast();
    // Check status + full register readback. Runs in a bounded SPI service,
    // not an arbitrarily blocking high-rate current ISR. Caller owns cadence.
    [[nodiscard]] bool check();
    // Explicit session teardown: inhibit, discard config/fault state. A new
    // safe wake/configuration is required; this never retries/rearms by itself.
    void reset_session();
    [[nodiscard]] bool configured() const { return configured_; }
    [[nodiscard]] bool coasted() const { return configured_ && coasted_; }
    // Last verified register state, not evidence of analog settling or a fresh
    // acquisition. Single-owner access only; the caller owns check() cadence.
    [[nodiscard]] bool calibrating() const { return configured_ && calibrating_; }
    [[nodiscard]] Drv8353Error error() const { return error_; }
    [[nodiscard]] Drv8353Faults faults() const { return faults_; }
    [[nodiscard]] std::uint8_t failed_address() const { return failed_address_; }

  private:
    // Board wake handoff verifies that it is retaining its own IO/session.
    friend class DriverWake;
    bool fail(Drv8353Error error, bool keep_fault_snapshot = false);
    bool permitted(bool quiet);
    bool read(std::uint8_t address, std::uint16_t &value, bool quiet);
    bool write_verify(std::uint8_t address, std::uint16_t value);
    bool read_faults(bool quiet);
    bool verify_all(bool quiet);
    bool set_current_calibration(bool active);
    Drv8353Io io_;
    Drv8353Registers expected_{};
    Drv8353Faults faults_{};
    Drv8353Error error_ = Drv8353Error::none;
    std::uint8_t failed_address_ = 0xff;
    bool configured_ = false, coasted_ = true, calibrating_ = false;
};
} // namespace odrive::mono56
