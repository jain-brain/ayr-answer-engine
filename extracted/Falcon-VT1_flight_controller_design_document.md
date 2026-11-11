## Falcon-VT1 Flight Controller

Design Document · Rev. A2 · Ayr Aerial Systems · Doc. No. DD-FVT1-A2

## 1. Overview

The Falcon-VT1 is a flight controller board for small VTOL fixed-wing UAVs, supporting up to 8 independent ESC channels, redundant IMUs, and a dedicated telemetry radio link. It is designed to drive the four thrust-generating devices used in tail-sitting VTOL transitions.

## 2. System Architecture

Figure 1 - Falcon-VT1 block diagram: sensor fusion, autopilot MCU, ESC driver bank, and RF telemetry.

<!-- image -->

Figure 1: :{
Figure 1: text":"Component IMU / GPS / Barometer is connected to the Flight Controller MCU (autopilot).","numeral":""}
Figure 1: {
Figure 1: text":"Component Flight Controller MCU (autopilot) receives input from IMU / GPS / Barometer and outputs to ESC Driver (x4-8 ch.), and transmits telemetry to RF Transceiver.","numeral":""}
Figure 1: {
Figure 1: text":"Component ESC Driver (x4-8 ch.) drives Brushless Motors and outputs power to the system.","numeral":""}
Figure 1: {
Figure 1: text":"Component Brushless Motors are driven by the ESC Driver (x4-8 ch.).","numeral":""}
Figure 1: {
Figure 1: text":"Component RF Transceiver receives telemetry from the Flight Controller MCU (autopilot).","numeral":""}
Figure 1: {
Figure 1: text":"Component Power Module receives power from the ESC Driver.","numeral":""}

The flight controller MCU fuses IMU, GPS, and barometric data at 400 Hz and outputs PWM/DShot commands to the ESC driver bank. The RF transceiver provides a bidirectional 915 MHz telemetry link to the ground control station for command uplink and status downlink.

## 3. Electrical Specifications

| Parameter                              | Value                     | Notes                    |
|----------------------------------------|---------------------------|--------------------------|
| Input voltage range                    | 9 - 26 V DC               | 2S-6S LiPo compatible    |
| Max continuous current per ESC channel | 40 A                      | 8 channels               |
| Peak current per ESC channel           | 60 A                      | 10 s max                 |
| Processor                              | Dual-core Cortex-M7 @ 480 | MHz with M4 co-processor |
| IMU update rate                        | 400 Hz                    | triple-redundant IMU     |
| Telemetry range                        | ≥ 15 km                   | line-of-sight, 915 MHz   |
| Operating temperature range            | -20 °C to 55 °C           | board ambient            |
| Dimensions                             | 68 x 46 x 14 mm           | excluding connectors     |
| Weight                                 | 38 g                      | board only               |

## 4. Known Limitations

The current revision (A2) does not provide hot-swap redundancy between the primary and secondary IMU; a failed primary IMU requires a reboot to switch. This is being addressed in Rev. B.