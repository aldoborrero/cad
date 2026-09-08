#include "drv8353.hpp"
#include <array>
#include <cstdlib>
#include <iostream>
#include <vector>

using namespace odrive::mono56;
namespace {
unsigned checks = 0;
void expect(bool ok, const char *message) {
    ++checks;
    if (!ok) {
        std::cerr << "FAIL: " << message << '\n';
        std::exit(1);
    }
}
Drv8353Config fixture() {
    // Illustrative register encoding, not qualified BSC027N10NS5A gate/OCP settings.
    return {150, 300, 150, 300, 2000, 200, 200, 2, 20, 250};
}
struct Chip {
    // Arbitrary initial register contents. No reliance on disputed reset OCP fields.
    std::array<uint16_t, 8> regs{0, 0, 0, 0x3ff, 0x7ff, 0x15d, 0x283, 0};
    std::vector<uint16_t> frames;
    bool awake = true, quiet = true, nfault = true;
    unsigned inhibited = 0, transfers = 0, fail_at = 0, permission_loss_at = 0;
    unsigned quiet_loss_at = 0, nfault_loss_at = 0, ignore_write_at = 0;
    unsigned corrupt_at = 0, corrupt_address = 0;
    uint16_t corrupt_mask = 0;
    int ignore_write_address = -1, forced_response = -1;
    static bool exchange(void *context, uint16_t tx, uint16_t *rx) {
        auto &c = *static_cast<Chip *>(context);
        ++c.transfers;
        c.frames.push_back(tx);
        if (c.transfers == c.fail_at)
            return false;
        const unsigned address = (tx >> 11) & 15;
        expect(address < 8, "never access an unlisted address");
        const uint16_t old = c.regs[address];
        *rx = c.forced_response >= 0 ? c.forced_response : static_cast<uint16_t>(0xa800 | old);
        if (!(tx & 0x8000)) {
            expect(address >= 2, "status registers never written");
            const uint16_t value = tx & 0x7ff;
            expect(address != 2 || !(value & 3), "never issue CLR_FLT or motor BRAKE action");
            expect(address != 7 || !(value & 0x7fe), "reserved calibration bits never set");
            const bool locked = ((c.regs[3] >> 8) & 7) == 6;
            if (static_cast<int>(address) != c.ignore_write_address &&
                c.transfers != c.ignore_write_at) {
                if (locked) {
                    if (address == 2)
                        c.regs[2] = (old & ~7u) | (value & 7);
                    if (address == 3 && (value >> 8) == 3)
                        c.regs[3] = (old & 0xff) | 0x300;
                } else if (address == 3) {
                    const auto lock = (value >> 8) == 6 ? 0x600 : 0x300;
                    c.regs[3] = lock | (value & 0xff);
                } else
                    c.regs[address] = value;
            }
        }
        if (c.transfers == c.permission_loss_at)
            c.awake = false;
        if (c.transfers == c.quiet_loss_at)
            c.quiet = false;
        if (c.transfers == c.nfault_loss_at)
            c.nfault = false;
        if (c.transfers == c.corrupt_at)
            c.regs[c.corrupt_address] ^= c.corrupt_mask;
        return true;
    }
    Drv8353Io io() {
        return {this,
                exchange,
                [](void *p) { return static_cast<Chip *>(p)->awake; },
                [](void *p) { return static_cast<Chip *>(p)->quiet; },
                [](void *p) { return static_cast<Chip *>(p)->nfault; },
                [](void *p) {
                    auto &c = *static_cast<Chip *>(p);
                    ++c.inhibited;
                    c.awake = false;
                }};
    }
};
void expect_failed(Drv8353 &driver, Chip &chip, Drv8353Error error) {
    expect(!driver.configured() && !driver.calibrating() && driver.error() == error &&
               chip.inhibited,
           "failure invalidates configuration and inhibits hardware");
    const auto count = chip.transfers;
    const auto original_faults = driver.faults();
    chip.awake = true;
    expect(!driver.configure_coasted(fixture()) && driver.error() == error,
           "first fault retained; no automatic restart");
    expect(chip.transfers == count, "faulted instance sends no more SPI frames");
    expect(driver.faults().valid == original_faults.valid &&
               driver.faults().packed() == original_faults.packed(),
           "first diagnostic snapshot retained");
}
} // namespace

int main() {
    Drv8353Registers regs;
    expect(make_drv8353_registers(fixture(), regs), "fixture fields accepted exactly");
    const std::array<uint16_t, 6> golden{0x484, 0x333, 0x233, 0x215, 0x280, 0};
    expect(regs.values == golden, "independent golden register words match TI field positions");
    for (auto gain : {5, 10, 20, 40}) {
        auto c = fixture();
        c.csa_gain = gain;
        expect(make_drv8353_registers(c, regs), "all four DRV8353 gains accepted");
        expect(((regs.values[4] >> 6) & 3) == (gain == 5    ? 0u
                                               : gain == 10 ? 1u
                                               : gain == 20 ? 2u
                                                            : 3u),
               "gain codes are 5/10/20/40, not DRV8301 codes");
    }
    for (int field = 0; field < 10; ++field) {
        auto c = fixture();
        switch (field) {
        case 0:
            c.hs_source_ma = 51;
            break;
        case 1:
            c.hs_sink_ma = 99;
            break;
        case 2:
            c.ls_source_ma = 1001;
            break;
        case 3:
            c.ls_sink_ma = 2001;
            break;
        case 4:
            c.drive_time_ns = 999;
            break;
        case 5:
            c.dead_time_ns = 101;
            break;
        case 6:
            c.vds_trip_mv = 61;
            break;
        case 7:
            c.ocp_deglitch_us = 3;
            break;
        case 8:
            c.csa_gain = 19;
            break;
        case 9:
            c.sense_trip_mv = 251;
            break;
        }
        Chip chip;
        Drv8353 d(chip.io());
        expect(!d.configure_coasted(c) && chip.transfers == 0,
               "invalid physical setting never reaches SPI");
        expect_failed(d, chip, Drv8353Error::invalid_config);
    }
    const std::vector<uint16_t> golden_frames{
        0x8000, 0x8800, 0xb800, 0x9000, 0x1004, 0x9000, 0x9800, 0x1bff, 0x9800, 0x1484, 0x9000,
        0x1b33, 0x9800, 0x2233, 0xa000, 0x2a15, 0xa800, 0x3280, 0xb000, 0x3800, 0xb800, 0x1e33,
        0x9800, 0x9000, 0x9800, 0xa000, 0xa800, 0xb000, 0xb800, 0x8000, 0x8800};
    {
        Chip chip;
        Drv8353 d(chip.io());
        expect(d.configure_coasted(fixture()) && d.coasted(),
               "configuration ends locked and COASTed");
        expect(chip.frames == golden_frames,
               "single-frame reads and explicit write readback sequence");
        expect(chip.regs[3] == 0x633 && chip.regs[5] == 0x215,
               "register lock and latched OCP active");
        expect(chip.regs[2] == 0x484 && chip.inhibited == 0,
               "config does not clear COAST or reset the driver");
        expect(d.release_coast() && !d.coasted() && d.configured(),
               "explicit release preserves initialized config");
        expect(chip.regs[2] == 0x480 && chip.regs[3] == 0x633,
               "COAST remains writable with config locked");
        chip.quiet = false;
        expect(d.check(),
               "runtime check permits PWM activity while retaining register protections");
        chip.regs[5] ^= 0x40; // Hypothetical reset/corruption selects retry mode.
        expect(!d.check(), "runtime register drift rejected");
        expect_failed(d, chip, Drv8353Error::readback_mismatch);
        d.reset_session();
        chip = Chip{};
        expect(d.configure_coasted(fixture()),
               "explicit new session and externally qualified wake can recover");
    }
    // Any transaction failure or permission loss during config must inhibit.
    for (unsigned index = 1; index <= golden_frames.size(); ++index) {
        Chip chip;
        chip.fail_at = index;
        Drv8353 d(chip.io());
        expect(!d.configure_coasted(fixture()),
               "transport failure at each config transaction rejected");
        expect_failed(d, chip, Drv8353Error::transport);
        Chip lost;
        lost.permission_loss_at = index;
        Drv8353 l(lost.io());
        expect(!l.configure_coasted(fixture()), "permission loss within transaction rejected");
        expect_failed(l, lost, Drv8353Error::permission_lost);
    }
    // Once COAST is cleared, any failed confirmation must still inhibit before
    // the caller gets a successful return and can enable its PWM timer.
    for (unsigned index = 1; index <= 12; ++index) {
        Chip chip;
        Drv8353 d(chip.io());
        expect(d.configure_coasted(fixture()), "release transport fixture configured");
        chip.fail_at = chip.transfers + index;
        expect(!d.release_coast(), "each failed release transaction inhibits");
        expect_failed(d, chip, Drv8353Error::transport);
    }
    for (unsigned address = 2; address <= 7; ++address) {
        Chip chip;
        Drv8353 d(chip.io());
        expect(d.configure_coasted(fixture()), "configuration drift fixture");
        chip.regs[address] ^= address == 2 ? 0x20 : 1;
        expect(!d.release_coast() && (chip.regs[2] & 4),
               "every configuration register checked before release");
        expect_failed(d, chip, Drv8353Error::readback_mismatch);
    }
    // Retain every bit from both status registers, including low VGS bits which
    // the old 8301 getter discarded from its second register.
    for (unsigned address = 0; address < 2; ++address)
        for (unsigned bit = 0; bit < 11; ++bit) {
            Chip chip;
            chip.regs[address] = 1u << bit;
            Drv8353 d(chip.io());
            expect(!d.configure_coasted(fixture()),
                   "every reported warning/fault inhibits configuration");
            expect(d.faults().valid && d.faults().packed() == (1u << (bit + 16 * address)),
                   "full two-register fault word preserved");
            expect_failed(d, chip, Drv8353Error::hardware_fault);
        }
    for (int response : {0, 0xffff}) {
        Chip chip;
        chip.forced_response = response;
        Drv8353 d(chip.io());
        expect(!d.configure_coasted(fixture()) && !d.configured() && chip.inhibited,
               "stuck-low or floating-high SPI cannot configure a driver");
    }
    {
        Chip chip;
        chip.ignore_write_address = 5;
        Drv8353 d(chip.io());
        expect(!d.configure_coasted(fixture()) && d.failed_address() == 5,
               "ignored OCP write fails readback");
        expect_failed(d, chip, Drv8353Error::readback_mismatch);
    }
    {
        Chip chip;
        chip.regs[7] = 2;
        Drv8353 d(chip.io());
        expect(!d.configure_coasted(fixture()), "unexpected reserved bits reject device state");
        expect_failed(d, chip, Drv8353Error::reserved_bits);
    }
    {
        Chip chip;
        chip.nfault = false;
        Drv8353 d(chip.io());
        expect(!d.configure_coasted(fixture()) && !d.faults().any(),
               "external nFAULT low also inhibits");
        expect_failed(d, chip, Drv8353Error::hardware_fault);
    }
    {
        Chip chip;
        chip.quiet = false;
        Drv8353 d(chip.io());
        expect(!d.configure_coasted(fixture()) && chip.transfers == 0,
               "cannot configure while PWM inputs active");
        expect_failed(d, chip, Drv8353Error::outputs_not_quiet);
    }
    {
        Chip chip;
        Drv8353 d(chip.io());
        expect(d.configure_coasted(fixture()), "release fault fixture");
        chip.regs[6] ^= 0x40;
        expect(!d.release_coast() && (chip.regs[2] & 4), "gain drift prevents release of COAST");
        expect_failed(d, chip, Drv8353Error::readback_mismatch);
    }
    {
        Chip chip;
        auto io = chip.io();
        io.exchange = nullptr;
        Drv8353 d(io);
        expect(!d.configure_coasted(fixture()), "missing IO callback rejected");
        expect_failed(d, chip, Drv8353Error::invalid_io);
    }
    {
        Chip chip;
        Drv8353 d(chip.io());
        expect(d.configure_coasted(fixture()) && d.faults().valid, "known-good status fixture");
        chip.awake = false;
        expect(!d.check() && !d.faults().valid,
               "old healthy status not presented as a new fault snapshot");
        expect_failed(d, chip, Drv8353Error::permission_lost);
    }
    // Independent SPI transcript: verify prior state, unlock, change only B/C
    // manual input shorts, relock, verify every register and final status.
    const std::vector<uint16_t> calibration_entry{
        0x8000, 0x8800, 0x9000, 0x9800, 0xa000, 0xa800, 0xb000, 0xb800, 0x1b33, 0x9800, 0x328c,
        0xb000, 0x1e33, 0x9800, 0x9000, 0x9800, 0xa000, 0xa800, 0xb000, 0xb800, 0x8000, 0x8800};
    auto calibration_exit = calibration_entry;
    calibration_exit[10] = 0x3280;
    {
        Chip chip;
        Drv8353 d(chip.io());
        expect(!d.calibrating() && d.configure_coasted(fixture()), "calibration fixture");
        const auto before = chip.regs;
        chip.frames.clear();
        expect(d.begin_current_calibration() && d.calibrating() && d.coasted(),
               "verified B/C calibration retains COAST");
        expect(chip.frames == calibration_entry, "calibration entry golden transcript");
        auto expected = before;
        expected[6] = 0x28c;
        expect(chip.regs == expected && chip.inhibited == 0,
               "only B/C input shorts change; A, gain, protections and lock preserved");
        expect(d.check() && d.calibrating(), "periodic check accepts intended manual mode");
        chip.frames.clear();
        expect(d.end_current_calibration() && !d.calibrating() && d.coasted(),
               "verified normal inputs restored without arming");
        expect(chip.frames == calibration_exit && chip.regs == before,
               "exit golden transcript restores exact original locked configuration");
        expect(d.begin_current_calibration() && d.end_current_calibration(),
               "a subsequent explicit calibration can run while still COASTed");
        expect(d.release_coast(), "arm step available only after restoring normal inputs");
    }
    for (auto gain : {5, 10, 20, 40}) {
        Chip chip;
        Drv8353 d(chip.io());
        auto c = fixture();
        c.csa_gain = gain;
        expect(d.configure_coasted(c), "gain-specific calibration fixture");
        const auto original = chip.regs[6];
        expect(d.begin_current_calibration() && chip.regs[6] == (original | 0x0c),
               "manual calibration preserves the selected gain");
        expect(d.end_current_calibration() && chip.regs[6] == original,
               "normal-input restoration preserves the selected gain");
    }
    for (bool exiting : {false, true}) {
        // Interrupt every transaction, including writes already applied and
        // post-write confirmation. Never attempt SPI cleanup/retry after fault.
        for (unsigned mode = 0; mode < 4; ++mode)
            for (unsigned step = 1; step <= calibration_entry.size(); ++step) {
                Chip chip;
                Drv8353 d(chip.io());
                expect(d.configure_coasted(fixture()), "transition fault fixture configured");
                if (exiting)
                    expect(d.begin_current_calibration(), "exit fault fixture calibrated");
                const unsigned at = chip.transfers + step;
                auto error = Drv8353Error::transport;
                if (mode == 0)
                    chip.fail_at = at;
                if (mode == 1) {
                    chip.permission_loss_at = at;
                    error = Drv8353Error::permission_lost;
                }
                if (mode == 2) {
                    chip.quiet_loss_at = at;
                    error = Drv8353Error::outputs_not_quiet;
                }
                if (mode == 3) {
                    chip.nfault_loss_at = at;
                    error = Drv8353Error::hardware_fault;
                }
                expect(!(exiting ? d.end_current_calibration() : d.begin_current_calibration()),
                       "fault at each entry/exit transaction rejects the transition");
                expect_failed(d, chip, error);
                const auto stopped = chip.transfers;
                expect(!d.begin_current_calibration() && !d.end_current_calibration() &&
                           chip.transfers == stopped && d.error() == error,
                       "failed transition cannot be used to retry or clean up over SPI");
            }
        for (unsigned step : {9, 11, 13}) {
            Chip chip;
            Drv8353 d(chip.io());
            expect(d.configure_coasted(fixture()), "ignored transition write fixture");
            if (exiting)
                expect(d.begin_current_calibration(), "ignored exit write fixture");
            chip.ignore_write_at = chip.transfers + step;
            expect(!(exiting ? d.end_current_calibration() : d.begin_current_calibration()),
                   "ignored unlock, CSA change or relock cannot report success");
            expect_failed(d, chip, Drv8353Error::readback_mismatch);
        }
        for (unsigned address = 2; address <= 7; ++address) {
            for (bool during : {false, true}) {
                Chip chip;
                Drv8353 d(chip.io());
                expect(d.configure_coasted(fixture()), "transition register drift fixture");
                if (exiting)
                    expect(d.begin_current_calibration(), "exit register drift fixture");
                const uint16_t mask = address == 2 ? 0x04 : (address == 3 ? 0x100 : 1);
                if (during) {
                    // Immediately after relock readback: only full final
                    // verification can detect this later register change.
                    chip.corrupt_at = chip.transfers + 14;
                    chip.corrupt_address = address;
                    chip.corrupt_mask = mask;
                } else
                    chip.regs[address] ^= mask;
                expect(!(exiting ? d.end_current_calibration() : d.begin_current_calibration()),
                       "full configuration drift before or during transition rejects it");
                expect_failed(d, chip, Drv8353Error::readback_mismatch);
            }
        }
    }
    for (unsigned misuse = 0; misuse < 6; ++misuse) {
        Chip chip;
        Drv8353 d(chip.io());
        if (misuse > 1)
            expect(d.configure_coasted(fixture()), "calibration state misuse fixture");
        if (misuse == 3 || misuse == 4)
            expect(d.begin_current_calibration(), "manual mode misuse fixture");
        if (misuse == 5)
            expect(d.release_coast(), "released bridge misuse fixture");
        const auto before = chip.transfers;
        bool result = false;
        if (misuse == 0 || misuse == 3 || misuse == 5)
            result = d.begin_current_calibration();
        if (misuse == 1 || misuse == 2)
            result = d.end_current_calibration();
        if (misuse == 4)
            result = d.release_coast();
        expect(!result && chip.transfers == before, "invalid transition never issues SPI");
        expect_failed(d, chip, Drv8353Error::invalid_state);
    }
    {
        Chip chip;
        Drv8353 d(chip.io());
        expect(d.configure_coasted(fixture()) && d.begin_current_calibration(),
               "active calibration check fixture");
        chip.quiet = false;
        const auto before = chip.transfers;
        expect(!d.check() && chip.transfers == before,
               "periodic check cannot accept active PWM during calibration");
        expect_failed(d, chip, Drv8353Error::outputs_not_quiet);
        d.reset_session();
        chip = Chip{};
        expect(!d.calibrating() && d.configure_coasted(fixture()) && d.begin_current_calibration(),
               "explicit reset and new wake/configuration discard old calibration state");
    }
    std::cout << checks
              << " DRV8353 configuration/fault checks passed with a simulated SPI device.\n";
}
