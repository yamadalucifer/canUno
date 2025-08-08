#include <mcp2515_can.h>
#include <SPI.h>

mcp2515_can CAN(9);

void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  if (CAN.begin(CAN_500KBPS) == CAN_OK) {
    Serial.println("CAN init OK!");
  } else {
    Serial.println("CAN init FAIL!");
    while (1)
      ;
  }
}

void loop() {
  // put your main code here, to run repeatedly:
  if (CAN.checkReceive() == CAN_MSGAVAIL) {
    long unsigned int rxId;
    unsigned char len;
    unsigned char rxBuf[8];
    CAN.readMsgBuf(&len, rxBuf);
    rxId = CAN.getCanId();
    Serial.print("ID: ");
    Serial.print(rxId, HEX);
    Serial.print(" Data: ");
    for (byte i = 0; i < len; i++) {
      Serial.print(rxBuf[i], HEX);
      Serial.print(" ");
    }
    Serial.println();
  }
}
