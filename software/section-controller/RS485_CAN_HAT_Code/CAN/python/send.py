import os
import can

os.system('sudo ip link set can0 type can bitrate 125000')
os.system('sudo ifconfig can0 up')

can0 = can.interface.Bus(channel = 'can0', interface = 'socketcan')# socketcan_native

msg = can.Message(arbitration_id=0x200, data=[2, 1, 2, 3, 4, 5, 6, 7], is_extended_id=False)
can0.send(msg)

os.system('sudo ifconfig can0 down')
