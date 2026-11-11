## RJA-40 Robotic Joint Actuator Module

Design Document · Rev. B · Ayr Robotics · Doc. No. DD-RJA40-B

## 1. Overview

The RJA-40 is an integrated brushless-motor joint actuator for collaborative robot arms, combining a BLDC motor, a two-stage planetary/harmonic drivetrain, an absolute encoder, and an onboard joint controller in a single module. It is designed for direct EtherCAT or CAN daisy-chaining across a 6- or 7-axis arm.

## 2. System Architecture

## Figure 1 — RJA-40 Actuator Drivetrain Block Diagram

Figure 1 - RJA-40 drivetrain block diagram: motor, gearbox, harmonic drive stage, output flange, encoder feedback, and joint controller.

<!-- image -->

Figure 1: BLDC Motor connects to Planetary Gearbox.
Figure 1: Planetary Gearbox drives Harmonic Drive Stage and also provides a connection to Absolute Encoder.
Figure 1: Harmonic Drive Stage drives Output Flange.
Figure 1: Absolute Encoder feeds Joint Controller.
Figure 1: Joint Controller drives EtherCAT / CAN Bus.

The absolute encoder reports output-flange position at 16-bit resolution to the joint controller, which closes a local current/velocity/position control loop at 4 kHz and exposes a CiA 402-style profile over EtherCAT or CAN to the arm's central controller.

## 3. Electrical &amp; Mechanical Specifications

| Parameter          | Value   | Notes                       |
|--------------------|---------|-----------------------------|
| Rated torque       | 40 N·m  | continuous, output flange   |
| Peak torque        | 120 N·m | 1 s max                     |
| Gear ratio         | 101:1   | planetary + harmonic stages |
| Rated output speed | 35 rpm  | continuous                  |

Figure 2 — RJA-40 Module (assembly photo)

| Operating voltage     | 48 V DC         | ±10%                      |
|-----------------------|-----------------|---------------------------|
| Continuous current    | 8 A             | bus current               |
| Peak current          | 22 A            | 1 s max                   |
| Encoder resolution    | 16-bit absolute | output side               |
| Backlash              | < 3 arcmin      | measured at output flange |
| Operating temperature | 0 °C to 50 °C   | housing surface           |
| Weight                | 1.35 kg         | module only               |
| Ingress protection    | IP54            | shaft seal fitted         |

Figure 2 - RJA-40 module, assembled view.

<!-- image -->

## 4. Known Limitations

The Rev. B module does not include an integrated torque sensor at the output flange; torque is estimated from motor current, which is less accurate under high-friction or high-backlash conditions. A strain-gauge-based torque sensor is planned for Rev. C.