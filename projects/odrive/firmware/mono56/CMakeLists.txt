cmake_minimum_required(VERSION 3.16)
project(odrive_mono56_components LANGUAGES C CXX)

add_library(mono56_measurement STATIC src/bus_voltage.cpp)
target_include_directories(mono56_measurement PUBLIC include)
target_compile_features(mono56_measurement PUBLIC cxx_std_17)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(mono56_measurement PRIVATE
        -Wall -Wextra -Werror -pedantic -fno-exceptions -fno-rtti)
endif()

add_library(mono56_supervision STATIC src/bus_supervision.cpp)
target_link_libraries(mono56_supervision PUBLIC mono56_measurement)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(mono56_supervision PRIVATE
        -Wall -Wextra -Werror -pedantic -fno-exceptions -fno-rtti)
endif()

add_library(mono56_current STATIC src/phase_current.cpp)
target_include_directories(mono56_current PUBLIC include)
target_compile_features(mono56_current PUBLIC cxx_std_17)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(mono56_current PRIVATE -Wall -Wextra -Werror -pedantic -fno-exceptions -fno-rtti)
endif()

option(MONO56_BUILD_TESTS "Build host component tests (not the board firmware)" ON)
add_library(mono56_pwm_plan STATIC src/pwm_sample_plan.cpp)
target_include_directories(mono56_pwm_plan PUBLIC include)
target_compile_features(mono56_pwm_plan PUBLIC cxx_std_17)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(mono56_pwm_plan PRIVATE -Wall -Wextra -Werror -pedantic -fno-exceptions -fno-rtti)
endif()
add_library(mono56_drv8353 STATIC src/drv8353.cpp)
target_include_directories(mono56_drv8353 PUBLIC include)
target_compile_features(mono56_drv8353 PUBLIC cxx_std_17)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(mono56_drv8353 PRIVATE
        -Wall -Wextra -Werror -pedantic -fno-exceptions -fno-rtti)
endif()
set(MONO56_CMSIS_ROOT "" CACHE PATH "STM32F4 CMSIS root containing Include and Device/ST")
if(MONO56_BUILD_TESTS)
    enable_testing()
    add_executable(memory_test src/memory.c tests/memory_test.c)
    target_compile_features(memory_test PRIVATE c_std_11)
    target_compile_definitions(memory_test PRIVATE memset=mono56_test_memset memcpy=mono56_test_memcpy)
    if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(memory_test PRIVATE -Wall -Wextra -Werror -pedantic -fno-builtin)
    endif()
    add_test(NAME memory COMMAND memory_test)
    add_executable(pwm_sample_plan_test tests/pwm_sample_plan_test.cpp)
    target_link_libraries(pwm_sample_plan_test PRIVATE mono56_pwm_plan)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(pwm_sample_plan_test PRIVATE -Wall -Wextra -Werror -pedantic)
    endif()
    add_test(NAME pwm_sample_plan COMMAND pwm_sample_plan_test)
    add_executable(phase_current_test tests/phase_current_test.cpp)
    target_link_libraries(phase_current_test PRIVATE mono56_current)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(phase_current_test PRIVATE -Wall -Wextra -Werror -pedantic)
    endif()
    add_test(NAME phase_current COMMAND phase_current_test)
    add_executable(bus_voltage_test tests/bus_voltage_test.cpp)
    target_link_libraries(bus_voltage_test PRIVATE mono56_measurement)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(bus_voltage_test PRIVATE -Wall -Wextra -Werror -pedantic)
    endif()
    add_test(NAME bus_voltage COMMAND bus_voltage_test)
    add_executable(drv8353_test tests/drv8353_test.cpp)
    target_link_libraries(drv8353_test PRIVATE mono56_drv8353)
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(drv8353_test PRIVATE -Wall -Wextra -Werror -pedantic)
    endif()
    add_test(NAME drv8353 COMMAND drv8353_test)
    if(MONO56_CMSIS_ROOT)
        if(NOT EXISTS "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include/stm32f405xx.h")
            message(FATAL_ERROR "MONO56_CMSIS_ROOT lacks the STM32F405 device header")
        endif()
        add_executable(adc23_acquisition_test
            src/adc23_acquisition.c src/adc1_acquisition.c tests/adc23_acquisition_test.cpp)
        target_compile_features(adc23_acquisition_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(adc23_acquisition_test PRIVATE MONO56_ADC23_TEST MONO56_ADC_TEST)
        target_include_directories(adc23_acquisition_test PRIVATE include tests)
        target_include_directories(adc23_acquisition_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(adc23_acquisition_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME adc23_acquisition COMMAND adc23_acquisition_test)
        add_executable(current_capture_test
            src/current_capture.c src/adc23_acquisition.c src/motor_inhibit.c
            tests/current_capture_test.cpp)
        target_compile_features(current_capture_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(current_capture_test PRIVATE
            MONO56_CURRENT_CAPTURE_TEST MONO56_MOTOR_TEST)
        target_include_directories(current_capture_test PRIVATE include tests)
        target_include_directories(current_capture_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(current_capture_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME current_capture COMMAND current_capture_test)
        add_executable(pwm_cycle_test
            src/pwm_cycle.cpp src/adc23_acquisition.c src/motor_inhibit.c
            tests/pwm_cycle_test.cpp)
        target_link_libraries(pwm_cycle_test PRIVATE mono56_pwm_plan)
        target_compile_features(pwm_cycle_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(pwm_cycle_test PRIVATE
            MONO56_PWM_CYCLE_TEST MONO56_CURRENT_CAPTURE_TEST MONO56_MOTOR_TEST)
        target_include_directories(pwm_cycle_test PRIVATE include tests)
        target_include_directories(pwm_cycle_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(pwm_cycle_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME pwm_cycle COMMAND pwm_cycle_test)
        add_executable(pwm_capture_test
            src/pwm_capture.cpp src/pwm_cycle.cpp src/current_capture.c src/adc23_acquisition.c src/motor_inhibit.c
            tests/pwm_capture_test.cpp)
        target_link_libraries(pwm_capture_test PRIVATE mono56_pwm_plan)
        target_compile_features(pwm_capture_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(pwm_capture_test PRIVATE
            MONO56_PWM_CAPTURE_TEST MONO56_PWM_CYCLE_TEST MONO56_CURRENT_CAPTURE_TEST MONO56_MOTOR_TEST)
        target_include_directories(pwm_capture_test PRIVATE include tests)
        target_include_directories(pwm_capture_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(pwm_capture_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME pwm_capture COMMAND pwm_capture_test)
        add_executable(adc1_acquisition_test
            src/adc1_acquisition.c tests/adc1_acquisition_test.cpp)
        target_compile_features(adc1_acquisition_test PRIVATE c_std_11)
        target_compile_definitions(adc1_acquisition_test PRIVATE MONO56_ADC_TEST)
        target_include_directories(adc1_acquisition_test PRIVATE tests)
        target_include_directories(adc1_acquisition_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        target_link_libraries(adc1_acquisition_test PRIVATE mono56_measurement)
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(adc1_acquisition_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME adc1_acquisition COMMAND adc1_acquisition_test)
        add_executable(bus_supervision_test
            src/adc1_acquisition.c src/motor_inhibit.c tests/bus_supervision_test.cpp)
        target_compile_features(bus_supervision_test PRIVATE c_std_11)
        target_compile_definitions(bus_supervision_test PRIVATE
            MONO56_ADC_TEST MONO56_MOTOR_TEST)
        target_include_directories(bus_supervision_test PRIVATE tests)
        target_include_directories(bus_supervision_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        target_link_libraries(bus_supervision_test PRIVATE mono56_supervision)
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(bus_supervision_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME bus_supervision COMMAND bus_supervision_test)
        add_executable(monitor_service_test
            src/adc1_acquisition.c src/motor_inhibit.c
            monitor/monitor.cpp tests/monitor_service_test.cpp)
        target_compile_features(monitor_service_test PRIVATE c_std_11)
        target_compile_definitions(monitor_service_test PRIVATE
            MONO56_ADC_TEST MONO56_MOTOR_TEST MONO56_MONITOR_TEST
            MONO56_BUS_PUBLICATION_TEST
            MONO56_MONITOR_UV=10.0f MONO56_MONITOR_OV=58.0f)
        target_include_directories(monitor_service_test PRIVATE tests monitor)
        target_include_directories(monitor_service_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        target_link_libraries(monitor_service_test PRIVATE mono56_supervision)
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(monitor_service_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME monitor_service COMMAND monitor_service_test)
        add_executable(spi3_transport_test src/spi3_transport.c tests/spi3_transport_test.cpp)
        target_compile_features(spi3_transport_test PRIVATE c_std_11)
        target_compile_definitions(spi3_transport_test PRIVATE MONO56_SPI_TEST)
        target_include_directories(spi3_transport_test PRIVATE tests)
        target_include_directories(spi3_transport_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        target_link_libraries(spi3_transport_test PRIVATE mono56_drv8353 mono56_current)
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(spi3_transport_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME spi3_transport COMMAND spi3_transport_test)
        add_executable(driver_io_test src/driver_io.c src/motor_inhibit.c
            src/driver_wake.cpp src/drv8353.cpp tests/driver_io_test.cpp)
        target_compile_features(driver_io_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(driver_io_test PRIVATE MONO56_DRIVER_IO_TEST)
        target_include_directories(driver_io_test PRIVATE include tests)
        target_include_directories(driver_io_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(driver_io_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME driver_io COMMAND driver_io_test)
        add_executable(current_monitor_test
            src/adc23_acquisition.c src/current_capture.c monitor/current_monitor.cpp
            src/adc1_acquisition.c src/motor_inhibit.c src/spi3_transport.c src/driver_io.c
            src/driver_wake.cpp monitor/monitor.cpp monitor/driver_monitor.cpp
            tests/driver_monitor_test.cpp)
        target_compile_features(current_monitor_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(current_monitor_test PRIVATE
            MONO56_ADC_TEST MONO56_MOTOR_TEST MONO56_SPI_TEST MONO56_DRIVER_IO_TEST
            MONO56_MONITOR_TEST MONO56_DIAGNOSTIC_TEST MONO56_MONITOR_DRIVER MONO56_MONITOR_CURRENT
            MONO56_MONITOR_UV=10.0f MONO56_MONITOR_OV=58.0f)
        target_include_directories(current_monitor_test PRIVATE include tests monitor)
        target_include_directories(current_monitor_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        target_link_libraries(current_monitor_test PRIVATE mono56_supervision mono56_drv8353 mono56_current)
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(current_monitor_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME current_monitor COMMAND current_monitor_test healthy)
        foreach(scenario missing_b missing_c adc_irq_loss noise csa_drift exit_loss supply_drift
                collection_timeout stale_frame supply_skew invalid_config foreground_stall uncertain_span post_fault)
            add_test(NAME current_monitor_${scenario} COMMAND current_monitor_test ${scenario})
        endforeach()
        add_executable(timing_monitor_test
            src/adc23_acquisition.c src/current_capture.c monitor/current_monitor.cpp
            src/pwm_cycle.cpp src/pwm_capture.cpp monitor/timing_monitor.cpp
            src/adc1_acquisition.c src/motor_inhibit.c src/spi3_transport.c src/driver_io.c
            src/driver_wake.cpp monitor/monitor.cpp monitor/driver_monitor.cpp
            tests/driver_monitor_test.cpp)
        target_compile_features(timing_monitor_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(timing_monitor_test PRIVATE
            MONO56_ADC_TEST MONO56_MOTOR_TEST MONO56_SPI_TEST MONO56_DRIVER_IO_TEST
            MONO56_MONITOR_TEST MONO56_DIAGNOSTIC_TEST MONO56_MONITOR_DRIVER MONO56_MONITOR_CURRENT MONO56_MONITOR_TIMING
            MONO56_MONITOR_UV=10.0f MONO56_MONITOR_OV=58.0f)
        target_include_directories(timing_monitor_test PRIVATE include tests monitor)
        target_include_directories(timing_monitor_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        target_link_libraries(timing_monitor_test PRIVATE mono56_supervision mono56_drv8353 mono56_current mono56_pwm_plan)
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(timing_monitor_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME timing_monitor COMMAND timing_monitor_test healthy)
        foreach(scenario missing_b missing_c adc_irq_loss update_irq_loss nfault brake bus_ov csa_drift foreground_stall
                timing_supply_skew timing_zero_age timing_supply_drift timing_stale_bus)
            add_test(NAME timing_monitor_${scenario} COMMAND timing_monitor_test ${scenario})
        endforeach()
        add_executable(driver_monitor_test
            src/adc1_acquisition.c src/motor_inhibit.c src/spi3_transport.c src/driver_io.c
            src/driver_wake.cpp monitor/monitor.cpp monitor/driver_monitor.cpp
            tests/driver_monitor_test.cpp)
        target_compile_features(driver_monitor_test PRIVATE c_std_11 cxx_std_17)
        target_compile_definitions(driver_monitor_test PRIVATE
            MONO56_ADC_TEST MONO56_MOTOR_TEST MONO56_SPI_TEST MONO56_DRIVER_IO_TEST
            MONO56_MONITOR_TEST MONO56_DIAGNOSTIC_TEST MONO56_MONITOR_DRIVER
            MONO56_MONITOR_UV=10.0f MONO56_MONITOR_OV=58.0f)
        target_include_directories(driver_monitor_test PRIVATE include tests monitor)
        target_include_directories(driver_monitor_test SYSTEM PRIVATE
            "${MONO56_CMSIS_ROOT}/Include"
            "${MONO56_CMSIS_ROOT}/Device/ST/STM32F4xx/Include")
        target_link_libraries(driver_monitor_test PRIVATE mono56_supervision mono56_drv8353)
        if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
            target_compile_options(driver_monitor_test PRIVATE -Wall -Wextra -Werror)
        endif()
        add_test(NAME driver_monitor COMMAND driver_monitor_test healthy)
        foreach(scenario bus_ov spi_loss nfault brake coast_drift foreground_stall stale_bus bus_timeout)
            add_test(NAME driver_monitor_${scenario} COMMAND driver_monitor_test ${scenario})
        endforeach()
    else()
        message(STATUS "ADC and supervisor peripheral tests omitted: supply MONO56_CMSIS_ROOT to run them")
    endif()
endif()
