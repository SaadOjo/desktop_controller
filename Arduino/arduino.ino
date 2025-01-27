/*******************************************************
 * Pin Assignments
 *******************************************************/
const int POT_PIN  = A3;
const int SW1_PIN  = 6;    // Switch 1 (pull-down, using internal pull-up)
const int SW2_PIN  = 7;    // Switch 2 (pull-down, using internal pull-up)
const int LED1_PIN = 9;    // LED 1
const int LED2_PIN = 10;   // LED 2

/*******************************************************
 * Debounce Configuration
 *******************************************************/
unsigned long lastDebounceTimeSW1 = 0;
unsigned long lastDebounceTimeSW2 = 0;
unsigned long debounceDelay = 30;  // milliseconds

bool sw1State = HIGH;  // with pull-up, "HIGH" = not pressed
bool sw2State = HIGH;
bool lastSw1Reading = HIGH;
bool lastSw2Reading = HIGH;

/*******************************************************
 * LED Control and Test Mode
 *******************************************************/
bool led1On = false;
bool led2On = false;
bool testMode = false; // when true, switches directly control LEDs

/*******************************************************
 * Continuous Transmit Mode + Threshold
 *******************************************************/
// Whether to automatically send changes (on by default)
bool continuousMode = true;

// Last reported states (so we only send changes)
int lastSw1Val = -1;  
int lastSw2Val = -1;  
int lastPotVal = -1;  

// Pot Schmitt trigger threshold
const int potThreshold = 5;  // only send pot changes > this difference

/*******************************************************
 * Setup
 *******************************************************/
void setup() {
  Serial.begin(9600);

  // Pin modes
  pinMode(POT_PIN, INPUT);

  // Switches: use internal pull-ups (so pin reads HIGH if not pressed)
  pinMode(SW1_PIN, INPUT_PULLUP);
  pinMode(SW2_PIN, INPUT_PULLUP);

  // LEDs
  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);

  // Start LEDs off
  digitalWrite(LED1_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);
}

/*******************************************************
 * Main Loop
 *******************************************************/
void loop() {
  // 1) Debounce the switches
  debounceSwitches();

  // 2) If test mode is on, let each switch directly drive its LED
  if (testMode) {
    // Pressed = LOW => LED ON
    digitalWrite(LED1_PIN, (sw1State == LOW) ? HIGH : LOW);
    digitalWrite(LED2_PIN, (sw2State == LOW) ? HIGH : LOW);
  } else {
    // Otherwise, use the last LED1/LED2 commands from serial
    digitalWrite(LED1_PIN, led1On ? HIGH : LOW);
    digitalWrite(LED2_PIN, led2On ? HIGH : LOW);
  }

  // 3) If continuous mode is enabled, send changed states as needed
  if (continuousMode) {
    sendChangedStates();
  }

  // 4) Handle any incoming serial commands
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // remove trailing \r or spaces
    parseCommand(command);
  }
}

/*******************************************************
 * Debounce Switches
 *******************************************************/
void debounceSwitches() {
  // Read raw pins
  int readingSW1 = digitalRead(SW1_PIN);
  int readingSW2 = digitalRead(SW2_PIN);

  // --- Switch 1 ---
  if (readingSW1 != lastSw1Reading) {
    lastDebounceTimeSW1 = millis();
  }
  if ((millis() - lastDebounceTimeSW1) > debounceDelay) {
    sw1State = readingSW1;
  }
  lastSw1Reading = readingSW1;

  // --- Switch 2 ---
  if (readingSW2 != lastSw2Reading) {
    lastDebounceTimeSW2 = millis();
  }
  if ((millis() - lastDebounceTimeSW2) > debounceDelay) {
    sw2State = readingSW2;
  }
  lastSw2Reading = readingSW2;
}

/*******************************************************
 * Send Only Changed States (Continuous Mode)
 *******************************************************/
void sendChangedStates() {
  // Convert to final "inverted" logic for reporting:
  //   Pressed (LOW)  => 0
  //   Not pressed => 1
  int currentSw1Val = (sw1State == LOW) ? 0 : 1;
  int currentSw2Val = (sw2State == LOW) ? 0 : 1;

  // Read pot
  int currentPotVal = analogRead(POT_PIN);

  // We'll build a single message but only with fields that changed
  String msg = "";
  bool somethingChanged = false;

  // Check SW1
  if (currentSw1Val != lastSw1Val) {
    msg += "SW1=";
    msg += currentSw1Val;
    msg += " ";
    lastSw1Val = currentSw1Val;
    somethingChanged = true;
  }

  // Check SW2
  if (currentSw2Val != lastSw2Val) {
    msg += "SW2=";
    msg += currentSw2Val;
    msg += " ";
    lastSw2Val = currentSw2Val;
    somethingChanged = true;
  }

  // Check POT (with threshold)
  if (lastPotVal < 0) {
    // If we haven't reported anything yet (-1), treat as changed
    msg += "POT=";
    msg += currentPotVal;
    msg += " ";
    lastPotVal = currentPotVal;
    somethingChanged = true;
  } else if (abs(currentPotVal - lastPotVal) >= potThreshold) {
    msg += "POT=";
    msg += currentPotVal;
    msg += " ";
    lastPotVal = currentPotVal;
    somethingChanged = true;
  }

  // If anything changed, send the single line
  if (somethingChanged) {
    msg.trim(); // remove trailing space
    Serial.println(msg);
  }
}

/*******************************************************
 * Parse and Execute Serial Commands
 *******************************************************/
void parseCommand(const String &cmd) {
  // Commands supported:
  //   GET        => respond once with: "SW1=0/1 SW2=0/1 POT=0..1023"
  //   LED1=0/1   => turn LED1 off/on
  //   LED2=0/1   => turn LED2 off/on
  //   TEST=0/1   => disable/enable test mode
  //   CONT=0/1   => disable/enable continuous mode

  if (cmd.equalsIgnoreCase("GET")) {
    // Report current states in one line
    int sw1Val = (sw1State == LOW) ? 0 : 1;  // inverted for reporting
    int sw2Val = (sw2State == LOW) ? 0 : 1;  // inverted for reporting
    int potVal = analogRead(POT_PIN);

    Serial.print("SW1=");
    Serial.print(sw1Val);
    Serial.print(" SW2=");
    Serial.print(sw2Val);
    Serial.print(" POT=");
    Serial.println(potVal);
  }
  else if (cmd.startsWith("LED1=")) {
    // e.g. "LED1=0" or "LED1=1"
    char val = cmd.charAt(5);
    if (val == '0') {
      led1On = false;
    } else if (val == '1') {
      led1On = true;
    }
  }
  else if (cmd.startsWith("LED2=")) {
    // e.g. "LED2=0" or "LED2=1"
    char val = cmd.charAt(5);
    if (val == '0') {
      led2On = false;
    } else if (val == '1') {
      led2On = true;
    }
  }
  else if (cmd.startsWith("TEST=")) {
    // "TEST=0" => false, "TEST=1" => true
    char val = cmd.charAt(5);
    if (val == '0') {
      testMode = false;
    } else if (val == '1') {
      testMode = true;
    }
  }
  else if (cmd.startsWith("CONT=")) {
    // "CONT=0" => disable continuous, "CONT=1" => enable continuous
    char val = cmd.charAt(5);
    if (val == '0') {
      continuousMode = false;
    } else if (val == '1') {
      continuousMode = true;
      // Force next cycle to transmit everything at least once
      lastSw1Val = -1;
      lastSw2Val = -1;
      lastPotVal = -1;
    }
  }
  else {
    Serial.println("Unknown command.");
  }
}
