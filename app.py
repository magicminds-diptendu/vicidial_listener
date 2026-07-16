from services.ami_service import AMIService

ami = AMIService()


@ami.on("NewCallerid")
def handle_new_call(event):
    print("Incoming Call")
    print(event.keys)


@ami.on("Hangup")
def handle_hangup(event):
    print("Call Ended")
    print(event.keys)


@ami.on("Newstate")
def handle_new_state(event):
    print(event.keys)


if __name__ == "__main__":
    ami.start()
