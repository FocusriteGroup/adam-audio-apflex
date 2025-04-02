/*
 * Headphone channel selector
 * By F Beu 09/02/2024
 * 
 * Connect the headphone amplifier to the input channel
 * Connect the headphones to channel 1 and 2 (both inputs to headphones)
 * 
 * Connect the USB and use a serial terminal program like putty or teraterm
 */

#define CHANNEL1 0
#define CHANNEL2 1
#define OPEN 1
#define CLOSE 0

#define relayPin 28        // Pin (GP28) connected to Relay    Output pin
#define BoxClosedPin 16    // Pin (GP16) connected to switch   Input pin
#define BoxOpenPin 17      // Pin (GP17) connected to switch   Output pin

String inputString = "";        // A String to hold incoming data
bool stringComplete = false;    // Whether the string is complete
bool currentChannel = CHANNEL1; // Current channel (default to CHANNEL1)
bool isBoxOpen = CLOSE;         // Box state (default to CLOSED)
bool lastBoxState = isBoxOpen;

void setup() {
  // Initialize serial communication
  Serial.begin(9600);
  inputString.reserve(200); // Reserve memory for the input string
  setupIO();
  WriteIO();
  delay(1000);
}

void loop() {
  SerialEvent();
  CheckPins();
}

//-----------------------------------------------------------------------------
// Check the state of the box pins
void CheckPins() {
  isBoxOpen = digitalRead(BoxClosedPin);
  if (lastBoxState != isBoxOpen) {
    Serial.println(isBoxOpen ? "Box open!" : "Box closed!");
    lastBoxState = isBoxOpen;
  }
}

//-----------------------------------------------------------------------------
// Open the box
void openBox() {
  digitalWrite(BoxOpenPin, HIGH);
  delay(2000);
  digitalWrite(BoxOpenPin, LOW);
}

//-----------------------------------------------------------------------------
// Handle serial commands
void SerialCommands() {
  if (inputString.length() > 1) { // Ignore empty commands
    inputString.toUpperCase();

    if (inputString.startsWith("CHANNEL_1")) {
      currentChannel = CHANNEL1;
      Serial.println("Channel is set to channel 1");
    } else if (inputString.startsWith("CHANNEL_2")) {
      currentChannel = CHANNEL2;
      Serial.println("Channel is set to channel 2");
    } else if (inputString.startsWith("OPEN_BOX")) {
      openBox();
      Serial.println("Box opened!");
    } else if (inputString.startsWith("VAL")) {
      // Combine channel and box status into a single response
      String response = (currentChannel == CHANNEL1 ? "Channel is set to channel 1" : "Channel is set to channel 2");
      response += ", ";
      response += (isBoxOpen ? "Box is open!" : "Box is closed!");
      Serial.println(response);
    } else {
      Serial.println("Unknown command.");
    }

    WriteIO();
  }
}

//-----------------------------------------------------------------------------
// Handle serial input
void SerialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;

    if (inChar == '\n') {
      stringComplete = true;
    }
  }

  if (stringComplete) {
    stringComplete = false;
    SerialCommands();
    inputString = "";
  }
}

//-----------------------------------------------------------------------------
// Set up the I/O pins
void setupIO() {
  pinMode(relayPin, OUTPUT);
  pinMode(BoxClosedPin, INPUT_PULLUP);
  pinMode(BoxOpenPin, OUTPUT);

  digitalWrite(relayPin, HIGH);
  digitalWrite(BoxOpenPin, LOW);
}

//-----------------------------------------------------------------------------
// Write the current channel state to the relay
void WriteIO() {
  digitalWrite(relayPin, currentChannel == CHANNEL1 ? LOW : HIGH);
}