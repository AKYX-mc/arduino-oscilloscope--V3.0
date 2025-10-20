/*
 * 重新定义电位器功能的示波器固件
 * - A3: 水平时基控制 (Time/Div)
 * - A4: 垂直时基控制 (Volt/Div) 
 * - A5: Y轴调整 (Vertical Position)
 * - 3通道信号: A0, A1, A2
 * - 10按钮: D2-D11
 */

#define SAMPLES_PER_CHAN 200
#define TOTAL_SAMPLES 600
#define BAUD_RATE 250000

void setup() {
  Serial.begin(BAUD_RATE);
  while (!Serial);
  
  // 配置10个按钮 (D2-D11) 为输入上拉
  for (int pin = 2; pin <= 11; pin++) {
    pinMode(pin, INPUT_PULLUP);
  }
}

void loop() {
  // 发送波形数据帧
  Serial.write(0xAA);
  Serial.write(0x55);
  
  for (int i = 0; i < SAMPLES_PER_CHAN; i++) {
    uint16_t v0 = analogRead(A0);
    uint16_t v1 = analogRead(A1);
    uint16_t v2 = analogRead(A2);
    
    Serial.write(lowByte(v0)); Serial.write(highByte(v0));
    Serial.write(lowByte(v1)); Serial.write(highByte(v1));
    Serial.write(lowByte(v2)); Serial.write(highByte(v2));
  }
  
  // 发送控制数据帧
  Serial.write(0xCC);
  Serial.write(0x33);
  
  // 3个电位器 (重新定义功能)
  int pot_time_base = analogRead(A3);    // A3: 水平时基 (Time/Div)
  int pot_volt_base = analogRead(A4);    // A4: 垂直时基 (Volt/Div)
  int pot_y_position = analogRead(A5);   // A5: Y轴调整 (Vertical Position)
  
  Serial.write(lowByte(pot_time_base)); Serial.write(highByte(pot_time_base));
  Serial.write(lowByte(pot_volt_base)); Serial.write(highByte(pot_volt_base));
  Serial.write(lowByte(pot_y_position)); Serial.write(highByte(pot_y_position));
  
  // 10个按钮 (D2-D11)
  for (int pin = 2; pin <= 11; pin++) {
    Serial.write(digitalRead(pin) == LOW ? 1 : 0);
  }
  
  delay(10);
}