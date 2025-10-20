# -*- coding: utf-8 -*-
"""
重新定义电位器功能的示波器上位机
- A3: 水平时基控制 (Time/Div)
- A4: 垂直时基控制 (Volt/Div)
- A5: Y轴调整 (Vertical Position)
- 保留软件扫描控制功能
- 10按钮完全支持
- 专业级显示
"""
import sys
import time
import serial
import serial.tools.list_ports
import math
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os

class OscilloscopeRedefined:
    def __init__(self, root):
        self.root = root
        self.root.title("专业示波器 - 重新定义电位器功能")
        self.root.geometry("1800x1000")
        
        # 配置
        self.BAUD_RATE = 250000
        self.SAMPLES_PER_CHAN = 200
        self.TOTAL_SAMPLES = 600
        self.WAVE_DATA_SIZE = 1200
        self.CTRL_DATA_SIZE = 16
        
        # 状态（重新定义电位器功能）
        self.is_running = False
        self.time_base = 1.0        # A3: 水平时基 (ms/div)
        self.volt_per_div = [1.0, 1.0, 1.0]  # A4: 垂直时基 (V/div) - 所有通道
        self.y_axis_position = 0.0  # A5: Y轴调整 (-2.5V to +2.5V)
        
        # 保留软件扫描控制（不连接电位器）
        self.scan_range = 1.0       # 软件UI控制
        self.scan_fine = 1.0        # 软件UI控制
        
        self.trigger_level = 2.5
        self.trigger_rising = True
        self.cursor_mode = False
        self.cursor_t1 = None
        self.cursor_t2 = None
        
        # 频率/电压显示
        self.channel_frequencies = [0.0, 0.0, 0.0]
        self.average_frequencies = [0.0, 0.0, 0.0]
        self.frequency_history = [[], [], []]
        self.cursor_voltages = [0.0, 0.0, 0.0]
        
        # 数据
        self.current_data = [[0.0] * self.SAMPLES_PER_CHAN for _ in range(3)]
        self.history = []
        self.last_buttons = [0] * 10
        
        # 串口
        self.serial_port = None
        self.serial_buffer = bytearray()
        self.serial_lock = threading.Lock()
        
        # 性能
        self.last_update = time.time()
        self.fps = 0.0
        self.sample_rate = 8000
        
        # 配置文件
        self.config_file = "oscilloscope_config.json"
        self.load_config()
        
        self.setup_ui()
        self.start_serial_thread()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.time_base = config.get('time_base', 1.0)
                    self.volt_per_div = config.get('volt_per_div', [1.0, 1.0, 1.0])
                    self.y_axis_position = config.get('y_axis_position', 0.0)
            except:
                pass

    def save_config(self):
        config = {
            'time_base': self.time_base,
            'volt_per_div': self.volt_per_div,
            'y_axis_position': self.y_axis_position
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except:
            pass

    def setup_ui(self):
        # 菜单栏
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="保存数据", command=self.save_data)
        file_menu.add_command(label="保存配置", command=self.save_config)
        menubar.add_cascade(label="文件", menu=file_menu)
        
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", width=350)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0,5))
        control_frame.pack_propagate(False)
        
        # 设备连接
        port_frame = ttk.LabelFrame(control_frame, text="设备连接")
        port_frame.pack(fill=tk.X, padx=5, pady=5)
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, state="readonly")
        self.port_combo.pack(fill=tk.X, padx=5, pady=2)
        self.refresh_ports()
        btn_frame = ttk.Frame(port_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(btn_frame, text="刷新", command=self.refresh_ports).pack(side=tk.LEFT, padx=(0,5))
        self.connect_btn = ttk.Button(btn_frame, text="连接", command=self.toggle_connection)
        self.connect_btn.pack(side=tk.LEFT)
        
        # 硬件控制（重新定义的电位器功能）
        hardware_frame = ttk.LabelFrame(control_frame, text="硬件控制 (电位器)")
        hardware_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(hardware_frame, text="A3: 水平时基 (ms/div):").pack(anchor=tk.W, padx=5)
        self.time_base_var = tk.DoubleVar(value=1.0)
        time_base_spin = ttk.Spinbox(hardware_frame, from_=0.1, to=100, increment=0.1,
                                    textvariable=self.time_base_var, width=10)
        time_base_spin.pack(fill=tk.X, padx=5, pady=2)
        self.time_base_var.trace('w', lambda *args: setattr(self, 'time_base', self.time_base_var.get()))
        
        ttk.Label(hardware_frame, text="A4: 垂直时基 (V/div):").pack(anchor=tk.W, padx=5)
        self.volt_base_var = tk.DoubleVar(value=1.0)
        volt_base_spin = ttk.Spinbox(hardware_frame, from_=0.01, to=5.0, increment=0.01,
                                    textvariable=self.volt_base_var, width=10)
        volt_base_spin.pack(fill=tk.X, padx=5, pady=2)
        self.volt_base_var.trace('w', lambda *args: self.update_volt_per_div(self.volt_base_var.get()))
        
        ttk.Label(hardware_frame, text="A5: Y轴调整 (V):").pack(anchor=tk.W, padx=5)
        self.y_position_var = tk.DoubleVar(value=0.0)
        y_position_spin = ttk.Spinbox(hardware_frame, from_=-2.5, to=2.5, increment=0.1,
                                     textvariable=self.y_position_var, width=10)
        y_position_spin.pack(fill=tk.X, padx=5, pady=2)
        self.y_position_var.trace('w', lambda *args: setattr(self, 'y_axis_position', self.y_position_var.get()))
        
        # 软件扫描控制（保留但不连接电位器）
        software_frame = ttk.LabelFrame(control_frame, text="软件扫描控制")
        software_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(software_frame, text="扫描范围:").pack(anchor=tk.W, padx=5)
        self.scan_range_var = tk.DoubleVar(value=1.0)
        scan_range_spin = ttk.Spinbox(software_frame, from_=0.1, to=100, increment=0.1,
                                     textvariable=self.scan_range_var, width=10)
        scan_range_spin.pack(fill=tk.X, padx=5, pady=2)
        self.scan_range_var.trace('w', lambda *args: setattr(self, 'scan_range', self.scan_range_var.get()))
        
        ttk.Label(software_frame, text="扫描微调:").pack(anchor=tk.W, padx=5)
        self.scan_fine_var = tk.DoubleVar(value=1.0)
        scan_fine_spin = ttk.Spinbox(software_frame, from_=0.8, to=1.2, increment=0.01,
                                    textvariable=self.scan_fine_var, width=10)
        scan_fine_spin.pack(fill=tk.X, padx=5, pady=2)
        self.scan_fine_var.trace('w', lambda *args: setattr(self, 'scan_fine', self.scan_fine_var.get()))
        
        # 触发设置
        trig_frame = ttk.LabelFrame(control_frame, text="触发设置")
        trig_frame.pack(fill=tk.X, padx=5, pady=5)
        self.trig_level_var = tk.DoubleVar(value=2.5)
        ttk.Label(trig_frame, text="触发电平 (V):").pack(anchor=tk.W, padx=5)
        trig_spin = ttk.Spinbox(trig_frame, from_=0, to=5, increment=0.1,
                               textvariable=self.trig_level_var, width=10)
        trig_spin.pack(fill=tk.X, padx=5, pady=2)
        self.trig_level_var.trace('w', lambda *args: setattr(self, 'trigger_level', self.trig_level_var.get()))
        
        # 通道控制
        for i in range(3):
            ch_frame = ttk.LabelFrame(control_frame, text=f"通道 {i+1} (A{i})")
            ch_frame.pack(fill=tk.X, padx=5, pady=5)
            enable_var = tk.BooleanVar(value=True)
            enable_cb = ttk.Checkbutton(ch_frame, text="启用", variable=enable_var)
            enable_cb.pack(anchor=tk.W, padx=5)
            setattr(self, f'ch{i}_enabled', enable_var)
        
        # 控制按钮
        btn_frame2 = ttk.Frame(control_frame)
        btn_frame2.pack(fill=tk.X, padx=5, pady=5)
        self.run_btn = ttk.Button(btn_frame2, text="开始采集", command=self.toggle_run)
        self.run_btn.pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="XY 模式", command=self.show_xy).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="历史回放", command=self.show_history).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="光标测量", command=self.toggle_cursor).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="自动设置", command=self.auto_scale).pack(fill=tk.X, pady=2)
        
        # 右侧显示区域
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 波形显示
        self.canvas = tk.Canvas(right_frame, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        self.canvas.bind('<Button-1>', self.on_canvas_click)
        
        # 底部面板
        bottom_frame = ttk.Frame(right_frame, height=150)
        bottom_frame.pack(fill=tk.X, pady=(5,0))
        bottom_frame.pack_propagate(False)
        
        # 频率/电压显示
        freq_frame = ttk.LabelFrame(bottom_frame, text="实时频率 & 电压")
        freq_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        self.freq_text = tk.Text(freq_frame, height=8, bg='black', fg='white', font=('Consolas', 9))
        self.freq_text.pack(fill=tk.BOTH, expand=True)
        
        # 统计面板
        stats_frame = ttk.LabelFrame(bottom_frame, text="自动测量")
        stats_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.stats_text = tk.Text(stats_frame, height=8, bg='black', fg='white', font=('Consolas', 9))
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪 | A3:水平时基 | A4:垂直时基 | A5:Y轴调整")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_volt_per_div(self, value):
        """更新所有通道的垂直时基"""
        for i in range(3):
            self.volt_per_div[i] = value

    def refresh_ports(self):
        ports = []
        for p in serial.tools.list_ports.comports():
            desc = p.description
            if 'Arduino' in desc or 'CH340' in desc or 'USB Serial' in desc:
                ports.insert(0, f"{p.device} - {desc}")
            else:
                ports.append(f"{p.device} - {desc}")
        if not ports:
            ports = ["未找到设备"]
        self.port_combo['values'] = ports
        self.port_combo.set(ports[0])

    def toggle_connection(self):
        if self.serial_port and self.serial_port.is_open:
            self.disconnect_serial()
            self.connect_btn.config(text="连接")
            self.run_btn.config(state='disabled')
        else:
            self.connect_serial()
            if self.serial_port and self.serial_port.is_open:
                self.connect_btn.config(text="断开")
                self.run_btn.config(state='normal')

    def connect_serial(self):
        try:
            port = self.port_var.get().split(' - ')[0]
            if port == "未找到设备":
                messagebox.showwarning("警告", "未找到串口设备！")
                return
            self.serial_port = serial.Serial(port, self.BAUD_RATE, timeout=0.01)
            self.status_var.set(f"✅ 已连接: {port} | 硬件控制就绪")
        except Exception as e:
            error_msg = "端口被占用" if "PermissionError" in str(e) else str(e)
            messagebox.showerror("连接错误", f"无法连接:\n{error_msg}")
            self.serial_port = None

    def disconnect_serial(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.serial_port = None
        self.status_var.set("❌ 已断开连接")

    def toggle_run(self):
        self.is_running = not self.is_running
        self.run_btn.config(text="停止采集" if self.is_running else "开始采集")

    def toggle_cursor(self):
        self.cursor_mode = not self.cursor_mode
        if self.cursor_mode:
            messagebox.showinfo("光标测量", "左键点击设置光标\n显示光标位置的实时电压")
            self.cursor_t1 = None
            self.cursor_t2 = None

    def on_canvas_resize(self, event):
        if event.widget == self.canvas:
            self.update_plot()

    def on_canvas_click(self, event):
        if not self.cursor_mode or not self.is_running:
            return
        canvas_width = self.canvas.winfo_width()
        if canvas_width <= 0:
            return
        actual_time_per_div = self.time_base
        total_time = actual_time_per_div * 10
        time_val = (event.x / canvas_width) * total_time
        if self.cursor_t1 is None:
            self.cursor_t1 = time_val
        elif self.cursor_t2 is None:
            self.cursor_t2 = time_val
        else:
            self.cursor_t1 = time_val
            self.cursor_t2 = None
        self.update_plot()
        self.update_cursor_voltages()

    # ========== 串口线程 ==========
    def serial_reader(self):
        while True:
            try:
                if self.serial_port and self.serial_port.is_open:
                    if self.serial_port.in_waiting:
                        with self.serial_lock:
                            raw_data = self.serial_port.read(self.serial_port.in_waiting)
                            self.serial_buffer.extend(raw_data)
                        self.root.after(0, self.process_serial_data)
                time.sleep(0.001)
            except Exception as e:
                time.sleep(0.1)

    def start_serial_thread(self):
        thread = threading.Thread(target=self.serial_reader, daemon=True)
        thread.start()

    def process_serial_data(self):
        if not self.serial_lock.acquire(blocking=False):
            return
        try:
            HEADER_WAVE = b'\xAA\x55'
            HEADER_CTRL = b'\xCC\x33'
            
            while len(self.serial_buffer) >= 2:
                idx = self.serial_buffer.find(HEADER_WAVE)
                if idx == -1:
                    break
                if len(self.serial_buffer) < idx + 2 + self.WAVE_DATA_SIZE:
                    break
                frame = self.serial_buffer[idx+2:idx+2+self.WAVE_DATA_SIZE]
                self.serial_buffer = self.serial_buffer[idx+2+self.WAVE_DATA_SIZE:]
                if len(frame) == self.WAVE_DATA_SIZE:
                    self.parse_waveform_frame(frame)
            
            while len(self.serial_buffer) >= 2:
                idx = self.serial_buffer.find(HEADER_CTRL)
                if idx == -1:
                    break
                if len(self.serial_buffer) < idx + 2 + self.CTRL_DATA_SIZE:
                    break
                frame = self.serial_buffer[idx+2:idx+2+self.CTRL_DATA_SIZE]
                self.serial_buffer = self.serial_buffer[idx+2+self.CTRL_DATA_SIZE:]
                if len(frame) == self.CTRL_DATA_SIZE:
                    self.parse_control_frame(frame)
        except Exception as e:
            print(f"数据处理错误: {e}")
        finally:
            self.serial_lock.release()

    def parse_waveform_frame(self, data):
        try:
            for i in range(self.SAMPLES_PER_CHAN):
                for ch in range(3):
                    idx = (i * 3 + ch) * 2
                    if idx + 1 < len(data):
                        adc_val = data[idx] + (data[idx+1] << 8)
                        voltage = adc_val * 5.0 / 1023.0
                        self.current_data[ch][i] = min(5.0, max(0.0, voltage))
            
            if len(self.history) >= 10:
                self.history.pop(0)
            self.history.append([row[:] for row in self.current_data])
            
            if self.is_running:
                current_time = time.time()
                if current_time - self.last_update > 0.016:
                    self.update_all_displays()
                    self.last_update = current_time
                    self.fps = 0.9 * self.fps + 0.1 * (1.0 / (current_time - self.last_update + 0.001))
        except Exception as e:
            print(f"波形解析错误: {e}")

    def parse_control_frame(self, data):
        """解析重新定义的电位器功能"""
        try:
            # 解析3个电位器（新功能定义）
            pot_time_raw = data[0] + (data[1] << 8)   # A3: 水平时基
            pot_volt_raw = data[2] + (data[3] << 8)   # A4: 垂直时基  
            pot_y_raw = data[4] + (data[5] << 8)      # A5: Y轴调整
            
            # A3: 水平时基 (0.1ms/div 到 100ms/div)
            if pot_time_raw <= 1:
                self.time_base = 0.1
            else:
                ratio = pot_time_raw / 1023.0
                log_min = math.log10(0.1)
                log_max = math.log10(100.0)
                self.time_base = 10 ** (log_min + ratio * (log_max - log_min))
                self.time_base = max(0.1, min(100.0, self.time_base))
            
            # A4: 垂直时基 (0.01V/div 到 5V/div)
            if pot_volt_raw <= 1:
                volt_div = 0.01
            else:
                ratio = pot_volt_raw / 1023.0
                log_min = math.log10(0.01)
                log_max = math.log10(5.0)
                volt_div = 10 ** (log_min + ratio * (log_max - log_min))
                volt_div = max(0.01, min(5.0, volt_div))
            
            # 应用到所有通道
            for i in range(3):
                self.volt_per_div[i] = volt_div
            
            # A5: Y轴调整 (-2.5V to +2.5V)
            self.y_axis_position = (pot_y_raw / 1023.0) * 5.0 - 2.5
            
            # 更新UI
            self.time_base_var.set(round(self.time_base, 3))
            self.volt_base_var.set(round(volt_div, 3))
            self.y_position_var.set(round(self.y_axis_position, 2))
            
            # 按钮处理
            buttons = [data[6 + i] for i in range(10)]
            btn_events = []
            for i in range(10):
                if buttons[i] == 1 and self.last_buttons[i] == 0:
                    btn_events.append(i)
            self.last_buttons = buttons
            self.handle_button_events(btn_events)
            
        except Exception as e:
            print(f"控制解析错误: {e}")

    def handle_button_events(self, btn_events):
        for btn in btn_events:
            if btn == 0:  # D2: Run/Stop
                self.toggle_run()
            elif btn == 1:  # D3: Trigger Slope
                self.trigger_rising = not self.trigger_rising
            elif btn == 2:  # D4: Channel Select
                self.cycle_channels()
            elif btn == 3:  # D5: Trigger Level +
                self.trigger_level = min(5.0, self.trigger_level + 0.1)
                self.trig_level_var.set(self.trigger_level)
            elif btn == 4:  # D6: Trigger Level -
                self.trigger_level = max(0.0, self.trigger_level - 0.1)
                self.trig_level_var.set(self.trigger_level)
            elif btn == 5:  # D7: Auto Scale
                self.auto_scale()
            elif btn == 6:  # D8: XY Mode
                self.show_xy()
            elif btn == 7:  # D9: History Playback
                self.show_history()
            elif btn == 8:  # D10: Cursor
                self.toggle_cursor()
            elif btn == 9:  # D11: Protocol Decode
                self.toggle_protocol_decode()

    def cycle_channels(self):
        enabled = [i for i in range(3) if getattr(self, f'ch{i}_enabled').get()]
        if len(enabled) == 3:
            for i in range(3):
                getattr(self, f'ch{i}_enabled').set(i == 0)
        elif len(enabled) == 1:
            current = enabled[0]
            next_ch = (current + 1) % 3
            for i in range(3):
                getattr(self, f'ch{i}_enabled').set(i == next_ch)
        else:
            for i in range(3):
                getattr(self, f'ch{i}_enabled').set(True)

    def auto_scale(self):
        if not self.is_running:
            return
        for i in range(3):
            if getattr(self, f'ch{i}_enabled').get():
                data = self.current_data[i]
                vpp = max(data) - min(data)
                if vpp > 0.1:
                    volt_div = max(0.01, vpp / 4.0)
                    self.volt_base_var.set(round(volt_div, 3))
                    self.update_volt_per_div(volt_div)
        messagebox.showinfo("自动设置", "已优化显示参数！")

    def toggle_protocol_decode(self):
        messagebox.showinfo("协议解码", "协议解码功能开发中...")

    # ========== 频率计算 ==========
    def calculate_frequency(self, data):
        if len(data) < 2:
            return 0.0
        
        mean_val = sum(data) / len(data)
        crossings = []
        for i in range(1, len(data)):
            if (data[i-1] < mean_val and data[i] >= mean_val) or \
               (data[i-1] > mean_val and data[i] <= mean_val):
                crossings.append(i)
        
        if len(crossings) < 2:
            return 0.0
        
        periods = []
        for i in range(1, len(crossings)):
            periods.append(crossings[i] - crossings[i-1])
        
        avg_period_samples = sum(periods) / len(periods) * 2
        if avg_period_samples <= 0:
            return 0.0
        
        frequency = self.sample_rate / avg_period_samples
        return frequency

    def update_cursor_voltages(self):
        if self.cursor_t1 is None:
            return
            
        actual_time_per_div = self.time_base
        total_time = actual_time_per_div * 10
        cursor_idx = min(int(self.cursor_t1 / total_time * self.SAMPLES_PER_CHAN), self.SAMPLES_PER_CHAN - 1)
        
        for ch in range(3):
            if getattr(self, f'ch{ch}_enabled').get():
                # 应用垂直缩放和Y轴调整
                raw_voltage = self.current_data[ch][cursor_idx]
                scaled_voltage = (raw_voltage * self.volt_per_div[ch]) + self.y_axis_position
                self.cursor_voltages[ch] = scaled_voltage
            else:
                self.cursor_voltages[ch] = 0.0

    # ========== 显示系统 ==========
    def update_all_displays(self):
        # 计算频率
        for ch in range(3):
            if getattr(self, f'ch{ch}_enabled').get():
                freq = self.calculate_frequency(self.current_data[ch])
                self.channel_frequencies[ch] = freq
                self.frequency_history[ch].append(freq)
                if len(self.frequency_history[ch]) > 10:
                    self.frequency_history[ch].pop(0)
                if self.frequency_history[ch]:
                    self.average_frequencies[ch] = sum(self.frequency_history[ch]) / len(self.frequency_history[ch])
            else:
                self.channel_frequencies[ch] = 0.0
                self.average_frequencies[ch] = 0.0
        
        self.update_plot()
        self.update_frequency_display()
        self.update_statistics()
        self.update_status()

    def update_plot(self):
        """使用重新定义的时基和垂直控制"""
        try:
            canvas = self.canvas
            canvas.delete("all")
            width = canvas.winfo_width()
            height = canvas.winfo_height()
            if width < 100 or height < 100:
                return
            
            # 使用 A3 电位器控制的水平时基
            actual_time_per_div = self.time_base
            total_time = actual_time_per_div * 10
            
            # 使用 A4 电位器控制的垂直缩放（每个通道可独立，但硬件同步）
            volt_scales = self.volt_per_div
            y_min = -2.5 * max(volt_scales)  # 使用最大缩放作为范围
            y_max = 2.5 * max(volt_scales)
            y_range = y_max - y_min
            
            # 绘制网格
            for i in range(11):
                x = (i / 10) * width
                canvas.create_line(x, 0, x, height, fill='#333333')
                if i % 2 == 0:
                    time_val = i * actual_time_per_div / 10
                    if time_val >= 10:
                        time_label = f"{time_val:.0f}"
                    elif time_val >= 1:
                        time_label = f"{time_val:.1f}"
                    elif time_val >= 0.1:
                        time_label = f"{time_val:.2f}"
                    else:
                        time_label = f"{time_val*1000:.0f}μs"
                    canvas.create_text(x, height-15, text=time_label, fill='white', font=('Arial', 8))
            
            for i in range(11):
                y_val = y_min + i * (y_max - y_min) / 10
                if y_min <= y_val <= y_max:
                    y = height - ((y_val - y_min) / y_range) * height
                    canvas.create_line(0, y, width, y, fill='#333333')
                    canvas.create_text(10, y, text=f"{y_val:.1f}", fill='white', font=('Arial', 8), anchor='w')
            
            # 绘制波形（应用垂直缩放和Y轴调整）
            colors = ['cyan', 'yellow', 'magenta']
            for ch in range(3):
                if getattr(self, f'ch{ch}_enabled').get():
                    points = []
                    for i in range(self.SAMPLES_PER_CHAN):
                        x = (i / (self.SAMPLES_PER_CHAN - 1)) * width
                        # 应用通道特定的垂直缩放和Y轴调整
                        voltage = (self.current_data[ch][i] * volt_scales[ch]) + self.y_axis_position
                        y = height - ((voltage - y_min) / y_range) * height
                        points.extend([x, y])
                    if len(points) >= 4:
                        canvas.create_line(points, fill=colors[ch], width=2)
            
            # 触发线（应用Y轴调整）
            trigger_voltage = (self.trigger_level * volt_scales[0]) + self.y_axis_position
            trigger_y = height - ((trigger_voltage - y_min) / y_range) * height
            canvas.create_line(0, trigger_y, width, trigger_y, fill='red', dash=(4, 4))
            
            # 光标
            if self.cursor_t1 is not None:
                x1 = (self.cursor_t1 / total_time) * width
                canvas.create_line(x1, 0, x1, height, fill='white', dash=(2, 2))
                if self.cursor_t2 is not None:
                    x2 = (self.cursor_t2 / total_time) * width
                    canvas.create_line(x2, 0, x2, height, fill='white', dash=(2, 2))
                    dt = abs(self.cursor_t2 - self.cursor_t1)
                    canvas.create_text((x1 + x2) / 2, 20, text=f"ΔT={dt:.2f}ms", fill='white')
            
            # 标题
            title = f"水平时基: {actual_time_per_div:.3f}ms/div | Y位置: {self.y_axis_position:+.2f}V"
            canvas.create_text(10, 10, text=title, fill='cyan', anchor='nw')
            
        except Exception as e:
            print(f"绘图错误: {e}")

    def update_frequency_display(self):
        try:
            self.freq_text.delete(1.0, tk.END)
            self.freq_text.insert(tk.END, "📊 实时频率 & 电压显示:\n\n")
            
            for ch in range(3):
                if getattr(self, f'ch{ch}_enabled').get():
                    real_freq = self.channel_frequencies[ch]
                    avg_freq = self.average_frequencies[ch]
                    cursor_volt = self.cursor_voltages[ch] if self.cursor_t1 is not None else 0.0
                    
                    self.freq_text.insert(tk.END, f"■ 通道 {ch+1} (A{ch}):\n")
                    self.freq_text.insert(tk.END, f"  实时频率: {real_freq:.2f} Hz\n")
                    self.freq_text.insert(tk.END, f"  平均频率: {avg_freq:.2f} Hz\n")
                    if self.cursor_t1 is not None:
                        self.freq_text.insert(tk.END, f"  光标电压: {cursor_volt:.3f} V\n")
                    self.freq_text.insert(tk.END, "\n")
                else:
                    self.freq_text.insert(tk.END, f"■ 通道 {ch+1} (A{ch}): 禁用\n\n")
        except Exception as e:
            print(f"频率显示错误: {e}")

    def update_statistics(self):
        try:
            self.stats_text.delete(1.0, tk.END)
            self.stats_text.insert(tk.END, "📈 自动测量结果:\n\n")
            
            for ch in range(3):
                if getattr(self, f'ch{ch}_enabled').get():
                    data = self.current_data[ch]
                    # 应用垂直缩放
                    scaled_data = [(v * self.volt_per_div[ch]) + self.y_axis_position for v in data]
                    vpp = max(scaled_data) - min(scaled_data)
                    vmax = max(scaled_data)
                    vmin = min(scaled_data)
                    vavg = sum(scaled_data) / len(scaled_data)
                    
                    self.stats_text.insert(tk.END, f"■ CH{ch+1}:\n")
                    self.stats_text.insert(tk.END, f"  Vpp:  {vpp:.3f} V\n")
                    self.stats_text.insert(tk.END, f"  Vmax: {vmax:.3f} V\n")
                    self.stats_text.insert(tk.END, f"  Vmin: {vmin:.3f} V\n")
                    self.stats_text.insert(tk.END, f"  Vavg: {vavg:.3f} V\n\n")
        except Exception as e:
            print(f"统计错误: {e}")

    def update_status(self):
        actual_time_per_div = self.time_base
        if actual_time_per_div >= 10:
            time_str = f"{actual_time_per_div:.0f}ms/div"
        elif actual_time_per_div >= 1:
            time_str = f"{actual_time_per_div:.1f}ms/div"
        elif actual_time_per_div >= 0.1:
            time_str = f"{actual_time_per_div:.2f}ms/div"
        else:
            time_str = f"{actual_time_per_div*1000:.1f}μs/div"
            
        self.status_var.set(f"水平时基: {time_str} | Y位置: {self.y_axis_position:+.2f}V | FPS: {self.fps:.1f}")

    # ========== 功能实现 ==========
    def show_xy(self):
        if not self.is_running:
            messagebox.showwarning("警告", "请先开始采集！")
            return
        xy_window = tk.Toplevel(self.root)
        xy_window.title("XY 模式")
        xy_window.geometry("800x600")
        canvas = tk.Canvas(xy_window, bg='black')
        canvas.pack(fill=tk.BOTH, expand=True)
        enabled = [i for i in range(3) if getattr(self, f'ch{i}_enabled').get()]
        if len(enabled) >= 2:
            x_data = self.current_data[enabled[0]]
            y_data = self.current_data[enabled[1]]
            points = []
            for i in range(min(len(x_data), len(y_data))):
                x = (x_data[i] / 5.0) * 800
                y = 600 - (y_data[i] / 5.0) * 600
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(points, fill='cyan', width=2)

    def show_history(self):
        if not self.history:
            messagebox.showwarning("警告", "无历史数据！")
            return
        hist_window = tk.Toplevel(self.root)
        hist_window.title("历史回放")
        hist_window.geometry("1000x600")
        canvas = tk.Canvas(hist_window, bg='black')
        canvas.pack(fill=tk.BOTH, expand=True)
        # 绘制历史波形...

    def save_data(self):
        if not self.is_running:
            messagebox.showwarning("警告", "请先开始采集！")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".csv")
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("Time,CH1,CH2,CH3\n")
                    actual_time_per_div = self.time_base
                    total_time = actual_time_per_div * 10
                    for i in range(self.SAMPLES_PER_CHAN):
                        t = i * (total_time / self.SAMPLES_PER_CHAN)
                        f.write(f"{t:.6f},{self.current_data[0][i]:.3f},{self.current_data[1][i]:.3f},{self.current_data[2][i]:.3f}\n")
                messagebox.showinfo("成功", "数据已保存！")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}")

    def on_closing(self):
        self.save_config()
        self.disconnect_serial()
        self.root.destroy()

# ========== 启动 ==========
if __name__ == "__main__":
    root = tk.Tk()
    app = OscilloscopeRedefined(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()