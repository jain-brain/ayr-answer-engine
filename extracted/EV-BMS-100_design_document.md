## EV-BMS-100 Battery Management System

Design Document · Rev. C · Ayr Powertrain Systems · Doc. No. DD-BMS-100-C

## 1. Overview

The EV-BMS-100 is a 96S lithium-ion battery management system for light commercial electric vehicle packs. It provides cell-level voltage and temperature monitoring, passive balancing, contactor control, and a CAN 2.0B interface to the vehicle ECU. The BMS MCU implements over-voltage, under-voltage, over-current, and over-temperature protection independently of the vehicle ECU.

## 2. System Architecture

Figure 1 — BMS System Block Diagram

<!-- image -->

Figure 1: Battery Pack (96S cells) feeds the Cell Voltage & Thermistor Monitor.
Figure 1: Cell Voltage & Thermistor Monitor is connected to the Battery Pack, to the BMS MCU, and to the Cell Balancing Circuit.
Figure 1: BMS MCU (safety core) receives input from the Cell Voltage & Thermistor Monitor and drives the CAN Transceiver and the Contactor Driver.
Figure 1: CAN Transceiver is driven by the BMS MCU and handles CAN 2.0B communication.
Figure 1: Cell Balancing Circuit is driven by the Cell Voltage & Thermistor Monitor.
Figure 1: Contactor Driver is driven by the BMS MCU and controls the Vehicle ECU.
Figure 1: Vehicle ECU is the downstream device controlled by the Contactor Driver.
Figure 1: CAN 2.0B indicates the CAN bus protocol used by the transceiver.

Figure 1 - BMS system block diagram showing the monitoring, balancing, and communication paths between the battery pack and the vehicle ECU.

The Cell Voltage &amp; Thermistor Monitor samples all 96 cell taps and 12 thermistor channels at 10 Hz and reports results to the BMS MCU over an isolated SPI link. The BMS MCU runs the safety state machine and issues balancing commands to the Cell Balancing Circuit and open/close commands to the Contactor Driver.

## 3. Electrical Specifications

| Parameter                   | Value              | Notes                       |
|-----------------------------|--------------------|-----------------------------|
| Nominal pack voltage        | 355.2 V            | 96S1P, 3.7 V/cell nominal   |
| Max charge current          | 120 A              | continuous, 150 A for 30 s  |
| Max discharge current       | 320 A              | continuous, 450 A for 10 s  |
| Cell balancing current      | 150 mA             | passive, per cell           |
| Overvoltage threshold       | 4.25 V/cell        | latching fault              |
| Undervoltage threshold      | 2.80 V/cell        | latching fault              |
| Isolation voltage           | ≥ 500 V DC         | pack-to-chassis             |
| Quiescent current (sleep)   | < 2 mA             | measured at 12 V aux supply |
| Communication protocol      | CAN 2.0B, 500 kbps | J1939-style PGNs            |
| Operating temperature range | -30 °C to 65 °C    | ambient, enclosure-mounted  |

## 4. Mechanical Specifications

| Parameter            | Value                  | Notes                |
|----------------------|------------------------|----------------------|
| Enclosure dimensions | 280 x 210 x 65 mm      | L x W x H            |
| Weight               | 2.4 kg                 | excluding harness    |
| Ingress protection   | IP67                   | connectors mated     |
| Mounting             | 4x M6 threaded inserts | 150 x 100 mm pattern |

Figure 2 — BMS Enclosure (rendering)

<!-- image -->

Figure 2: Component M12 connector x4 is shown on the front face of the rectangular block as four circular ports.
Figure 2: The four ports correspond to four M12 connectors as indicated by the label M12 connector x4.
Figure 2: There are no arrows or other connections depicted in the figure.
Figure 2: The connectors are arranged in a horizontal row across the front face of the block.

Figure 2 - BMS enclosure rendering showing the four M12 connector ports (pack sense, power, CAN, and auxiliary 12 V).

## 5. Known Limitations

The current hardware revision (Rev. C) does not support active balancing; balancing energy is dissipated as heat across bleed resistors. A future Rev. D is planned to add active balancing via a flyback topology, which is expected to improve pack-level capacity utilization by 2-3%.