from canbus.interface import CanInterface
from canbus.protocol import decode, encode_led_set
from app.bridge import Bridge

if __name__ == "__main__":
    # creation of controller instance 
    Controller = Bridge(54)

    try:
        Controller.start()
    except Exception:
        pass

    try:
        Controller.run()
    except Exception:
        pass

    # need to add code to handle turning off the controller
    # also need to save the section_id number for each pi so that if we turn it off it never
    # forgets what number it is

