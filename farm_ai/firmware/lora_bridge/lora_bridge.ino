/*
 * LoRa <-> USB-serial bridge for the gateway   (ESP32 + SX1276 plugged into the Raspberry Pi/laptop)   *** NOT yet tested on hardware ***
 *   radio  -> serial :  RX,<rssi>,<payload>\n
 *   serial -> radio  :  TX,<payload>\n        (send quickly: the node only listens ~1.5 s after it transmits)
 * Must use the same radio settings as the field node (868 MHz, SF9, BW125, CR4/5, CRC on).
 */
#include <SPI.h>
#include <LoRa.h>
#define LORA_SS 5
#define LORA_RST 14
#define LORA_DIO0 2
void setup() {
  Serial.begin(115200);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  while (!LoRa.begin(868E6)) delay(500);
  LoRa.setSpreadingFactor(9); LoRa.setSignalBandwidth(125E3); LoRa.setCodingRate4(5); LoRa.setTxPower(14); LoRa.enableCrc();
}
void loop() {
  if (LoRa.parsePacket()) {
    String s = ""; while (LoRa.available()) s += (char)LoRa.read();
    Serial.print("RX,"); Serial.print(LoRa.packetRssi()); Serial.print(","); Serial.println(s);
  }
  if (Serial.available()) {
    String l = Serial.readStringUntil('\n'); l.trim();
    if (l.startsWith("TX,")) { LoRa.beginPacket(); LoRa.print(l.substring(3)); LoRa.endPacket(); LoRa.receive(); }
  }
}
