### SECTION CONTROLLER 

The section controller module will be the medium point between the server and each node. It will manage all communications to and from the server to each node. Communication to the server will be over Wi-Fi, which many modern stadiums already have fully implemented, and to every node will be over a CAN bus using the CAN 2.0B protocol. The Wi-Fi communication will sue 2 different protocols: MQTT for control signals and RTP over UDP for the low-latency live audio stream.

Some of the main functions will be:


- Receive control messages over Wi-Fi.
- Generate a CAN frame with the new control signals and send it to the CAN module over SPI to propagate in the CAN bus.
- Receive CAN frames from the nodes.
- Send received information to the server over Wi-Fi.
- Get the live audio streams over Wi-Fi and connect them to the audio distribution lines by generating a differential signal.


This controller will consist of 2 main components: a Raspberry Pi 3B+ and a RS485 and CAN module for Raspberry pi and will require a 5V line with a minimum of 2.5A to power it.   

The prototyping and construction methods will start with building a strong codebase to build many of the other features on top of. This means getting functional CAN interface libraries for the Raspberry Pi and getting the MQTT Wi-Fi protocol communication working with the server, as well as the RTP over UDP protocol for the audio streaming. After all basic communications works well, I can build the actual CAN frame generator, Audio processor, and all other features mentioned above.

Testing for this module will be performed in parallel with feature implementation to get a faster deployment time. This will be done by directly testing with other modules and thus tackling integration from the beginning.
