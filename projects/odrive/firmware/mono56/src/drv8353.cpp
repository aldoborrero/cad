#include "drv8353.hpp"

namespace odrive::mono56 {
namespace {
constexpr std::uint16_t data_mask = 0x07ff;
constexpr std::uint16_t coast = 1u << 2;
constexpr std::uint16_t lock_mask = 7u << 8;
constexpr std::uint16_t unlocked = 3u << 8;
constexpr std::uint16_t locked = 6u << 8;
constexpr std::uint16_t calibrate_bc = (1u << 3) | (1u << 2);
constexpr std::uint16_t source_ma[] = {50,  50,  100, 150, 300, 350, 400, 450,
                                       550, 600, 650, 700, 850, 900, 950, 1000};
constexpr std::uint16_t sink_ma[] = {100,  100,  200,  300,  600,  700,  800,  900,
                                     1100, 1200, 1300, 1400, 1700, 1800, 1900, 2000};
constexpr std::uint16_t drive_ns[] = {500, 1000, 2000, 4000};
constexpr std::uint16_t dead_ns[] = {50, 100, 200, 400};
constexpr std::uint16_t vds_mv[] = {60,  70,  80,  90,  100, 200,  300,  400,
                                    500, 600, 700, 800, 900, 1000, 1500, 2000};
constexpr std::uint16_t deglitch_us[] = {1, 2, 4, 8};
constexpr std::uint16_t gains[] = {5, 10, 20, 40};
constexpr std::uint16_t sense_mv[] = {250, 500, 750, 1000};
template <unsigned N> int code(std::uint16_t value, const std::uint16_t (&choices)[N]) {
    for (unsigned i = 0; i < N; ++i)
        if (choices[i] == value)
            return i;
    return -1;
}
} // namespace

bool make_drv8353_registers(const Drv8353Config &c, Drv8353Registers &result) {
    result = {};
    const int hp = code(c.hs_source_ma, source_ma), hn = code(c.hs_sink_ma, sink_ma);
    const int lp = code(c.ls_source_ma, source_ma), ln = code(c.ls_sink_ma, sink_ma);
    const int drive = code(c.drive_time_ns, drive_ns), dead = code(c.dead_time_ns, dead_ns);
    const int vds = code(c.vds_trip_mv, vds_mv), deg = code(c.ocp_deglitch_us, deglitch_us);
    const int gain = code(c.csa_gain, gains), sense = code(c.sense_trip_mv, sense_mv);
    if (hp < 0 || hn < 0 || lp < 0 || ln < 0 || drive < 0 || dead < 0 || vds < 0 || deg < 0 ||
        gain < 0 || sense < 0)
        return false;
    result.values = {
        // All-bridge OCP action, report OTW, protections ON, six-PWM, COAST.
        static_cast<std::uint16_t>((1u << 10) | (1u << 7) | coast),
        static_cast<std::uint16_t>(unlocked | (hp << 4) | hn),
        static_cast<std::uint16_t>((drive << 8) | (lp << 4) | ln),   // CBC=0
        static_cast<std::uint16_t>((dead << 8) | (deg << 4) | vds),  // OCP_MODE=00
        static_cast<std::uint16_t>((1u << 9) | (gain << 6) | sense), // SPx shunt, VREF/2
        0 // Manual calibration, all reserved bits remain zero.
    };
    return true;
}

bool Drv8353::fail(Drv8353Error error, bool keep_fault_snapshot) {
    if (error_ == Drv8353Error::none) {
        error_ = error;
        if (!keep_fault_snapshot)
            faults_.valid = false;
    }
    configured_ = false;
    calibrating_ = false;
    if (io_.inhibit)
        io_.inhibit(io_.context);
    return false;
}

bool Drv8353::permitted(bool quiet) {
    if (!io_.exchange || !io_.awake_and_permitted || !io_.outputs_quiet || !io_.nfault_high ||
        !io_.inhibit)
        return fail(Drv8353Error::invalid_io);
    if (error_ != Drv8353Error::none)
        return fail(error_);
    if (!io_.awake_and_permitted(io_.context))
        return fail(Drv8353Error::permission_lost);
    if (quiet && !io_.outputs_quiet(io_.context))
        return fail(Drv8353Error::outputs_not_quiet);
    return true;
}

bool Drv8353::read(std::uint8_t address, std::uint16_t &value, bool quiet) {
    failed_address_ = address;
    if (!permitted(quiet))
        return false;
    std::uint16_t response = 0xffff;
    // DRV8353 responds with this register's data within the SAME frame.
    if (!io_.exchange(io_.context, static_cast<std::uint16_t>(0x8000u | (address << 11)),
                      &response))
        return fail(Drv8353Error::transport);
    if (!permitted(quiet))
        return false;
    value = response & data_mask; // Bits 15..11 are explicitly don't-care.
    return true;
}

bool Drv8353::write_verify(std::uint8_t address, std::uint16_t value) {
    failed_address_ = address;
    if (!permitted(true))
        return false;
    if (!io_.nfault_high(io_.context))
        return fail(Drv8353Error::hardware_fault);
    std::uint16_t old_value;
    if (!io_.exchange(io_.context, static_cast<std::uint16_t>((address << 11) | value), &old_value))
        return fail(Drv8353Error::transport);
    // Write response is the OLD register value; verify using a separate read.
    std::uint16_t actual;
    if (!read(address, actual, true))
        return false;
    if (actual != value)
        return fail(Drv8353Error::readback_mismatch);
    if (!io_.nfault_high(io_.context))
        return fail(Drv8353Error::hardware_fault);
    return true;
}

bool Drv8353::read_faults(bool quiet) {
    faults_.valid = false;
    std::uint16_t first, second;
    if (!read(0, first, quiet) || !read(1, second, quiet))
        return false;
    faults_ = {first, second, true};
    if (faults_.any() || !io_.nfault_high(io_.context))
        return fail(Drv8353Error::hardware_fault, true);
    return true;
}

bool Drv8353::verify_all(bool quiet) {
    for (std::uint8_t address = 2; address <= 7; ++address) {
        std::uint16_t actual;
        if (!read(address, actual, quiet))
            return false;
        if (actual != expected_.values[address - 2])
            return fail(Drv8353Error::readback_mismatch);
    }
    return true;
}

bool Drv8353::configure_coasted(const Drv8353Config &config) {
    if (configured_ || error_ != Drv8353Error::none)
        return fail(Drv8353Error::invalid_state);
    if (!make_drv8353_registers(config, expected_))
        return fail(Drv8353Error::invalid_config);
    if (!permitted(true) || !read_faults(true))
        return false;
    std::uint16_t calibration;
    if (!read(7, calibration, true))
        return false;
    if (calibration & 0x07fe)
        return fail(Drv8353Error::reserved_bits);
    // COAST is writable even while locked. First preserve the current control
    // settings while forcing COAST and avoiding BRAKE/CLR_FLT actions.
    std::uint16_t control;
    if (!read(2, control, true))
        return false;
    if (!write_verify(2, (control & ~3u) | coast))
        return false;
    // Unlock by changing ONLY LOCK, preserving current HS drive strengths.
    std::uint16_t hs;
    if (!read(3, hs, true))
        return false;
    if (!write_verify(3, (hs & ~lock_mask) | unlocked))
        return false;
    for (std::uint8_t address = 2; address <= 7; ++address) {
        if (!write_verify(address, expected_.values[address - 2]))
            return false;
    }
    expected_.values[1] = (expected_.values[1] & ~lock_mask) | locked;
    if (!write_verify(3, expected_.values[1]))
        return false;
    if (!verify_all(true) || !read_faults(true))
        return false;
    configured_ = true;
    coasted_ = true;
    calibrating_ = false;
    failed_address_ = 0xff;
    return true;
}

bool Drv8353::set_current_calibration(bool active) {
    if (!configured_ || !coasted_ || calibrating_ == active || error_ != Drv8353Error::none)
        return fail(Drv8353Error::invalid_state);
    // Includes CAL_MODE=0, CSA gain/mode, COAST and the existing register lock.
    // Never adopt a foreign configuration or auto-calibration mode as baseline.
    if (!permitted(true) || !read_faults(true) || !verify_all(true))
        return false;
    const auto csa = static_cast<std::uint16_t>(active ? expected_.values[4] | calibrate_bc
                                                       : expected_.values[4] & ~calibrate_bc);
    const auto hs_unlocked =
        static_cast<std::uint16_t>((expected_.values[1] & ~lock_mask) | unlocked);
    if (!write_verify(3, hs_unlocked) || !write_verify(6, csa) ||
        !write_verify(3, expected_.values[1]))
        return false;
    expected_.values[4] = csa;
    if (!verify_all(true) || !read_faults(true))
        return false;
    calibrating_ = active;
    failed_address_ = 0xff;
    return true;
}

bool Drv8353::begin_current_calibration() { return set_current_calibration(true); }
bool Drv8353::end_current_calibration() { return set_current_calibration(false); }

bool Drv8353::release_coast() {
    if (!configured_ || !coasted_ || calibrating_ || error_ != Drv8353Error::none)
        return fail(Drv8353Error::invalid_state);
    if (!permitted(true) || !read_faults(true) || !verify_all(true))
        return false;
    const auto enabled_control = static_cast<std::uint16_t>(expected_.values[0] & ~coast);
    if (!write_verify(2, enabled_control) || !read_faults(true))
        return false;
    expected_.values[0] = enabled_control;
    coasted_ = false;
    failed_address_ = 0xff;
    return true;
}

bool Drv8353::check() {
    if (!configured_ || error_ != Drv8353Error::none)
        return fail(Drv8353Error::invalid_state);
    // Manual input-short calibration never authorizes PWM activity.
    const bool quiet = calibrating_;
    if (!permitted(quiet) || !read_faults(quiet) || !verify_all(quiet) || !read_faults(quiet))
        return false;
    failed_address_ = 0xff;
    return true;
}

void Drv8353::reset_session() {
    if (io_.inhibit)
        io_.inhibit(io_.context);
    configured_ = false;
    coasted_ = true;
    calibrating_ = false;
    error_ = Drv8353Error::none;
    faults_ = {};
    failed_address_ = 0xff;
    expected_ = {};
}
} // namespace odrive::mono56
