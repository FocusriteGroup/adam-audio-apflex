/*
 * Headphone Channel Selector
 * Author: Thilo Rode
 * Date: 02/04/2025
 * Company: ADAM Audio GmbH
 *
 * Description:
 * This program controls a headphone channel selector with the following features:
 * - Two channels (Channel 1 and Channel 2) can be selected.
 * - The box can be opened via a command or external signal.
 * - The current status (channel and box state) is output as a 2-bit value.
 * - Multicore functionality is used to handle blocking tasks (e.g., opening the box) on Core 1.
 *
 * Features:
 * - Serial commands to control the system:
 *   - "SET_CHANNEL_1": Switch to Channel 1.
 *   - "SET_CHANNEL_2": Switch to Channel 2.
 *   - "OPEN_BOX": Open the box (handled on Core 1).
 *   - "GET_STATUS": Output the current status as a 2-bit value.
 * - Status output:
 *   - Bit 0: Box state (0 = Closed, 1 = Open).
 *   - Bit 1: Channel (0 = Channel 1, 1 = Channel 2).
 *
 * Hardware:
 * - Raspberry Pi Pico with RP2040 microcontroller.
 * - Relay connected to GP28 for channel switching.
 * - Switch connected to GP16 to detect box state (closed/open).
 * - Output pin GP17 to control the box opening mechanism.
 */

#include "pico/multicore.h" // For multicore support

#define relayPin 28        // Pin (GP28) connected to the relay (output pin)
#define BoxClosedPin 16    // Pin (GP16) connected to the box state switch (input pin)
#define BoxOpenPin 17      // Pin (GP17) connected to the box opening mechanism (output pin)

enum Channel { One, Two };     // Define channel states
enum BoxStatus { Closed, Open }; // Define box states

Channel channel;               // Current channel (set in setup())
BoxStatus boxStatus;           // Current box state (set in setup())

// Function executed on Core 1
void core1Task() {
  while (true) {
    // Wait for a signal from Core 0
    if (multicore_fifo_pop_blocking() == 1) {
      openBox(); // Open the box
    }
  }
}

void setup() {
  // Start the serial monitor
  Serial.begin(9600);

  // Configure pins
  pinMode(relayPin, OUTPUT);
  pinMode(BoxClosedPin, INPUT_PULLUP); // Input pin with pull-up resistor
  pinMode(BoxOpenPin, OUTPUT);

  // Set initial states
  digitalWrite(BoxOpenPin, LOW); // Set BoxOpenPin to LOW initially
  setChannel(One);               // Set default channel to Channel 1

  // Read and initialize the box state
  boxStatus = getBoxStatus();
  outputStatus(); // Output the initial status

  // Start Core 1
  multicore_launch_core1(core1Task);
}

void loop() {
  // Check if data is available on the serial interface
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n'); // Read command until newline
    command.trim(); // Remove whitespace and newline characters

    // Process the command
    processCommand(command);
  }

  // Monitor the box state
  BoxStatus currentBoxStatus = getBoxStatus();
  if (currentBoxStatus != boxStatus) {
    boxStatus = currentBoxStatus;
    outputStatus(); // Output status if the box state changes
  }
}

void setChannel(Channel newChannel) {
  // Set the channel and control the relay
  if (channel != newChannel) { // Only execute if the channel changes
    channel = newChannel;
    digitalWrite(relayPin, channel == One ? LOW : HIGH);
    outputStatus(); // Output status if the channel changes
  }
}

BoxStatus getBoxStatus() {
  // Read the current box state (directly from BoxClosedPin)
  return digitalRead(BoxClosedPin) == LOW ? Closed : Open;
}

void openBox() {
  // Open the box electrically
  digitalWrite(BoxOpenPin, HIGH); // Activate the mechanism
  delay(2000);                    // Wait for 2 seconds
  digitalWrite(BoxOpenPin, LOW);  // Deactivate the mechanism
}

void processCommand(String command) {
  if (command == "SET_CHANNEL_1") {
    setChannel(One);
  } else if (command == "SET_CHANNEL_2") {
    setChannel(Two);
  } else if (command == "OPEN_BOX") {
    // Send a signal to Core 1
    multicore_fifo_push_blocking(1);
  } else if (command == "GET_STATUS") {
    outputStatus(); // Output status when requested
  }
}

void outputStatus() {
  // Encode and output the status as 2 bits
  int status = (channel == Two ? 0b10 : 0b00) | (boxStatus == Open ? 0b01 : 0b00);
  Serial.println(status, BIN); // Output the status as a binary number
}