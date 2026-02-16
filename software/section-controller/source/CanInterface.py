import can
import os
import json

class CanInterface:
    # Constructor function. Creates a can object from the python-can library with the input 
    # arguments for channel and bustype
    def __init__(self, channel='can0', bustype='socketcan'):
        os.system('sudo ip link set can0 type can bitrate 100000')
        os.system('sudo ifconfig can0 up')
        self.channel = channel
        self.bus = can.interface.Bus(channel=channel, bustype=bustype)
    
    def send(self, message):
        self.bus.send(message)
    
    def run_receive(self, timeout = 0.01):
        message = self.bus.recv(timeout)
        return message
    
    def create_json(self, data: bytes, arbitration_id: int):
        # Your implementation here
        pass

    def shutdown(self):
        self.bus.shutdown()
        return