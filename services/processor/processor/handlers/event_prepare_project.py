"""
Ensure that the project has all the required things in both Ayon and Shotgrid,
mostly Custom Attributes.
"""

REGISTER_EVENT_TYPE = ["Shotgun_Project_New"]

def process_event(payload):
    """Entry point of the processor"""
    if not payload:
        logging.error("The Even payload is empty!")
        raise InputError
    print("Hello Received the Payload...")
    print(payload)



