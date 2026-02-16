import os
import can
from CanInterface import CanInterface

can = CanInterface

can.run_receive(timeout = 0.1)

