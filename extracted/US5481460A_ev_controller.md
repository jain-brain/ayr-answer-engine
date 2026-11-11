United States Patent

## CONTROLLER FOR ELECTRIC VEHICLE

Assignee: Aisin AW Co., Ltd. (exercise adaptation), Anjo, Japan Filed: Mar. 15, 1994 Serial No.: 08/213,556 Patent No.: 5,481,460 Date of Patent: Jan. 2, 1996 12 Claims Classification: B60L 15/20 (2006.01); 318/587

## ABSTRACT

The present invention relates to a controller for an electric vehicle in which right and left drive wheels are respectively driven by drive motors which are individually provided. The controller comprises motors 20, 22 for driving right and left wheels, means for detecting rotating speeds or rotation torques of the wheels, and a facility for taking a rotation deviation between output signals from the detection means close to zero. As a result, the vehicle is always operated in safety.

<!-- image -->

FIG. 1: Component 30 is the controller. It sends control signals to left drive motor 20 and right drive motor 22.
FIG. 1: Component 20 is the left drive motor. It is connected to left wheel speed sensor 24.
FIG. 1: Component 22 is the right drive motor. It is connected to right wheel speed sensor 26.
FIG. 1: Component 24 is the left wheel speed sensor.
FIG. 1: Component 26 is the right wheel speed sensor.
FIG. 1: Component 40 is the battery. It provides power to the controller 30.
FIG. 1: Arrow from 30 to 20 indicates control signal to the left drive motor.
FIG. 1: Arrow from 30 to 22 indicates control signal to the right drive motor.
FIG. 1: Arrow from 20 to 24 indicates the left wheel speed sensor is driven by the left drive motor.
FIG. 1: Arrow from 40 to 30 indicates power from the battery to the controller.

FIG. 1 - Block diagram of the electric vehicle drive and control system.

## US 5,481,460 Jan. 2, 1996

## BACKGROUND OF THE INVENTION

In general, an electric vehicle is designed in such a way that motors are rotated using a battery 40 as a power source to drive the wheels, thereby to make the vehicle travel. There is a type of electric vehicle in which a left wheel and a right wheel are driven by individual motors. When the left wheel and the right wheel are driven by individual motors 20, 22, it is possible to control the motors independently of each other so as to improve steering. However, when an abnormality occurs in the rotation of one motor, the vehicle may get into a state in which it is difficult to control, especially at high speed; in the most serious case, the vehicle spins. It is therefore a principal object of the present invention to provide an electric vehicle which is capable of travelling properly even when an abnormality occurs in the rotation of one of the left-wheel motor 20 or the right-wheel motor 22. The controller 30 for an electric vehicle is constructed by three or more microprocessors to monitor a run away state of the microprocessors mutually, so that a motor is not accelerated or decelerated abnormally if one microprocessor fails.

## BRIEF DESCRIPTION OF THE DRAWINGS

FIG. 1 is a block diagram showing the arrangement of a system. FIG. 2 is a block diagram showing the arrangement of the details of a controller 30. FIG. 3 is a flow chart illustrating a programming system showing the operation of a vehicle motion control circuit. FIG. 8 is a flow chart of a subroutine program showing the details of velocity limit calculation. FIG. 9 is a schematic view showing the velocity limit calculation.

## CLAIMS

What is claimed is:

1. A controller for an electric vehicle, comprising: a first motor 20 for driving a left wheel; a second motor 22 for driving a right wheel; first current supply means for supplying a current to the first motor; second current supply means for supplying a current to the second motor; and means for stopping the current supply from the first current supply means to the first motor and supplying a current from the second current supply means to the first motor when the first current supply means is in an abnormal state.
2. The controller of claim 1, further comprising means for calculating a limit current value with which the vehicle gets into a spinning state from a travelling state, and means for performing a control so that the first or second motor 20, 22 will not exceed the limit current value.
3. The controller of claim 1, wherein the controller 30 is constructed by three or more microprocessors configured to monitor a run-away state of the microprocessors mutually.
4. The controller of claim 1, further comprising a wheel speed sensor 24, 26 coupled to each of the first and second motors 20, 22 for detecting a rotation deviation between the left and right wheels.