# -*- coding: utf-8 -*-
"""
终极增强版示波器 - 完整功能集（含设置菜单 + 专业功能）
- ✅ 硬件时基生效（A3/A4）
- ✅ X轴软件缩放、暂停、抓取波形、F11全屏
- ✅ 设置菜单：个性化 + 专业功能
- 扫描范围/微调 (软件控制)
- 每通道实时/平均频率电压显示
- 自动归零 (一键校准)
- 升级XY模式
- 超宽时基范围 + 完整自动测量
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

# ========== 新增：设置对话框 ==========
class SettingsDialog:
    def __init__(self, parent, app):
        self.app = app
        self.window = tk.Toplevel(parent)
        self.window.title("设置")
        self.window.geometry("600x500")
        self.window.transient(parent)
        self.window.grab_set()

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ========== 个性化选项 ==========
        personal_frame = ttk.Frame(notebook)
        notebook.add(personal_frame, text="个性化")

        # 主题
        ttk.Label(personal_frame, text="主题:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.theme_var = tk.StringVar(value=self.app.config.get('theme', 'dark'))
        ttk.Radiobutton(personal_frame, text="暗色", variable=self.theme_var, value='dark').grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(personal_frame, text="亮色", variable=self.theme_var, value='light').grid(row=0, column=2, sticky=tk.W)

        # 波形颜色
        ttk.Label(personal_frame, text="波形颜色:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.color_vars = []
        default_colors = ['cyan', 'yellow', 'magenta']
        for i in range(3):
            ttk.Label(personal_frame, text=f"CH{i+1}").grid(row=2+i, column=0, sticky=tk.W, padx=5)
            var = tk.StringVar(value=self.app.config.get(f'color_ch{i}', default_colors[i]))
            self.color_vars.append(var)
            ttk.Entry(personal_frame, textvariable=var, width=15).grid(row=2+i, column=1, sticky=tk.W, padx=5)

        # 网格密度
        ttk.Label(personal_frame, text="网格密度:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        self.grid_density_var = tk.StringVar(value=self.app.config.get('grid_density', 'normal'))
        ttk.Combobox(personal_frame, textvariable=self.grid_density_var, values=['sparse', 'normal', 'dense'], state='readonly', width=12).grid(row=5, column=1, sticky=tk.W)

        # 字体大小
        ttk.Label(personal_frame, text="字体大小:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        self.font_size_var = tk.IntVar(value=self.app.config.get('font_size', 9))
        ttk.Spinbox(personal_frame, from_=8, to=14, textvariable=self.font_size_var, width=5).grid(row=6, column=1, sticky=tk.W)

        # ========== 专业功能 ==========
        pro_frame = ttk.Frame(notebook)
        notebook.add(pro_frame, text="专业功能")

        # 数学通道
        ttk.Label(pro_frame, text="数学通道:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.math_op_var = tk.StringVar(value=self.app.config.get('math_operation', 'none'))
        ops = ['none', 'CH1+CH2', 'CH1-CH2', 'CH1*CH2', 'FFT(CH1)']
        ttk.Combobox(pro_frame, textvariable=self.math_op_var, values=ops, state='readonly', width=15).grid(row=0, column=1, sticky=tk.W)

        # 参考波形
        ref_frame = ttk.Frame(pro_frame)
        ref_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=10)
        ttk.Button(ref_frame, text="保存当前为参考", command=self.save_reference).pack(side=tk.LEFT, padx=5)
        ttk.Button(ref_frame, text="清除参考", command=self.clear_reference).pack(side=tk.LEFT, padx=5)
        self.show_ref_var = tk.BooleanVar(value=self.app.config.get('show_reference', False))
        ttk.Checkbutton(pro_frame, text="显示参考波形", variable=self.show_ref_var).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5)

        # 触发模式
        ttk.Label(pro_frame, text="触发模式:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.trigger_mode_var = tk.StringVar(value=self.app.config.get('trigger_mode', 'edge'))
        modes = ['edge', 'pulse_width', 'video']
        ttk.Combobox(pro_frame, textvariable=self.trigger_mode_var, values=modes, state='readonly', width=15).grid(row=3, column=1, sticky=tk.W)

        # 数据导出
        ttk.Label(pro_frame, text="导出格式:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        self.export_format_var = tk.StringVar(value=self.app.config.get('export_format', 'csv'))
        ttk.Combobox(pro_frame, textvariable=self.export_format_var, values=['csv', 'txt'], state='readonly', width=15).grid(row=4, column=1, sticky=tk.W)

        # 按钮
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="应用", command=self.apply_settings).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.window.destroy).pack(side=tk.RIGHT, padx=5)

    def save_reference(self):
        self.app.reference_waveform = [row[:] for row in self.app.current_data]
        messagebox.showinfo("参考波形", "已保存当前波形为参考！")

    def clear_reference(self):
        self.app.reference_waveform = None
        messagebox.showinfo("参考波形", "参考波形已清除。")

    def apply_settings(self):
        # 保存到app.config
        self.app.config['theme'] = self.theme_var.get()
        for i in range(3):
            self.app.config[f'color_ch{i}'] = self.color_vars[i].get()
        self.app.config['grid_density'] = self.grid_density_var.get()
        self.app.config['font_size'] = self.font_size_var.get()
        self.app.config['math_operation'] = self.math_op_var.get()
        self.app.config['show_reference'] = self.show_ref_var.get()
        self.app.config['trigger_mode'] = self.trigger_mode_var.get()
        self.app.config['export_format'] = self.export_format_var.get()

        # 应用主题
        bg = 'white' if self.theme_var.get() == 'light' else 'black'
        fg = 'black' if self.theme_var.get() == 'light' else 'white'
        self.app.canvas.configure(bg=bg)
        self.app.freq_text.configure(bg=bg, fg=fg)
        self.app.measure_text.configure(bg=bg, fg=fg)
        # 更新字体
        font_name = 'Consolas' if sys.platform == 'win32' else 'Monospace'
        self.app.freq_text.configure(font=(font_name, self.font_size_var.get()))
        self.app.measure_text.configure(font=(font_name, self.font_size_var.get()))

        # 保存配置
        self.app.save_config()
        messagebox.showinfo("设置", "设置已应用！")
        self.window.destroy()


class UltimateOscilloscopeFinal:
    def __init__(self, root):
        self.root = root
        self.root.title("终极增强版示波器 - 完整功能集")
        self.root.geometry("1920x1080")
        # 配置
        self.BAUD_RATE = 250000
        self.SAMPLES_PER_CHAN = 200
        self.TOTAL_SAMPLES = 600
        self.WAVE_DATA_SIZE = 1200
        self.CTRL_DATA_SIZE = 16
        # 状态
        self.is_running = False
        self.time_base = 1.0        # 超宽时基范围（由硬件A3控制）
        self.volt_per_div = [1.0, 1.0, 1.0]
        self.y_axis_position = 0.0
        self.scan_range = 1.0
        self.scan_fine = 1.0
        self.dc_offset = [0.0, 0.0, 0.0]
        self.trigger_level = 2.5
        self.trigger_rising = True
        self.cursor_mode = False
        self.cursor_t1 = None
        self.cursor_t2 = None
        self.xy_mode = False
        self.xy_ch_x = 0
        self.xy_ch_y = 1
        # 频率/电压显示
        self.channel_frequencies = [0.0, 0.0, 0.0]
        self.average_frequencies = [0.0, 0.0, 0.0]
        self.channel_voltages = [0.0, 0.0, 0.0]
        self.average_voltages = [0.0, 0.0, 0.0]
        self.frequency_history = [[], [], []]
        self.voltage_history = [[], [], []]
        # 自动测量
        self.measurements = {
            'vpp': [0.0, 0.0, 0.0],
            'vmax': [0.0, 0.0, 0.0],
            'vmin': [0.0, 0.0, 0.0],
            'vavg': [0.0, 0.0, 0.0],
            'vrms': [0.0, 0.0, 0.0],
            'frequency': [0.0, 0.0, 0.0],
            'period': [0.0, 0.0, 0.0],
            'rise_time': [0.0, 0.0, 0.0]
        }
        # 数据
        self.current_data = [[0.0] * self.SAMPLES_PER_CHAN for _ in range(3)]
        self.history = []
        self.last_buttons = [0] * 10
        self.reference_waveform = None
        # 串口
        self.serial_port = None
        self.serial_buffer = bytearray()
        self.serial_lock = threading.Lock()
        # 性能
        self.last_update = time.time()
        self.fps = 0.0
        self.sample_rate = 8000
        # 配置
        self.config_file = "oscilloscope_config.json"
        # ========== 新增状态 ==========
        self.x_scale = 1.0
        self.acq_mode = "RUN"
        self.single_triggered = False
        self.fullscreen = False
        # ========== 初始化配置字典 ==========
        self.config = {
            'theme': 'dark',
            'color_ch0': 'cyan',
            'color_ch1': 'yellow',
            'color_ch2': 'magenta',
            'grid_density': 'normal',
            'font_size': 9,
            'math_operation': 'none',
            'show_reference': False,
            'trigger_mode': 'edge',
            'export_format': 'csv'
        }
        self.load_config()
        self.setup_ui()
        self.start_serial_thread()
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.exit_fullscreen)

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    saved = json.load(f)
                    self.time_base = saved.get('time_base', 1.0)
                    self.volt_per_div = saved.get('volt_per_div', [1.0, 1.0, 1.0])
                    self.y_axis_position = saved.get('y_axis_position', 0.0)
                    self.scan_range = saved.get('scan_range', 1.0)
                    self.scan_fine = saved.get('scan_fine', 1.0)
                    self.dc_offset = saved.get('dc_offset', [0.0, 0.0, 0.0])
                    self.x_scale = saved.get('x_scale', 1.0)
                    # 加载新设置
                    settings = saved.get('settings', {})
                    if settings:
                        self.config.update(settings)
                        # 应用主题
                        bg = 'white' if self.config['theme'] == 'light' else 'black'
                        fg = 'black' if self.config['theme'] == 'light' else 'white'
                        font_name = 'Consolas' if sys.platform == 'win32' else 'Monospace'
                        self.canvas.configure(bg=bg)
                        self.freq_text.configure(bg=bg, fg=fg, font=(font_name, self.config['font_size']))
                        self.measure_text.configure(bg=bg, fg=fg, font=(font_name, self.config['font_size']))
            except Exception as e:
                print(f"加载配置失败: {e}")

    def save_config(self):
        config = {
            'time_base': self.time_base,
            'volt_per_div': self.volt_per_div,
            'y_axis_position': self.y_axis_position,
            'scan_range': self.scan_range,
            'scan_fine': self.scan_fine,
            'dc_offset': self.dc_offset,
            'x_scale': self.x_scale,
            'settings': self.config
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def setup_ui(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="保存数据", command=self.save_data)
        file_menu.add_command(label="保存配置", command=self.save_config)
        menubar.add_cascade(label="文件", menu=file_menu)
        measure_menu = tk.Menu(menubar, tearoff=0)
        measure_menu.add_command(label="自动测量", command=self.show_measurements)
        measure_menu.add_command(label="光标测量", command=self.toggle_cursor)
        measure_menu.add_command(label="自动归零", command=self.auto_zero)
        menubar.add_cascade(label="测量", menu=measure_menu)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="XY模式", command=self.toggle_xy_mode)
        menubar.add_cascade(label="视图", menu=view_menu)
        # ========== 新增设置菜单 ==========
        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="选项", command=self.open_settings)
        menubar.add_cascade(label="设置", menu=settings_menu)

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        control_frame = ttk.LabelFrame(main_frame, text="控制面板", width=400)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0,5))
        control_frame.pack_propagate(False)

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

        scan_frame = ttk.LabelFrame(control_frame, text="软件扫描控制")
        scan_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(scan_frame, text="扫描范围 (ms/div):").pack(anchor=tk.W, padx=5)
        self.scan_range_var = tk.DoubleVar(value=1.0)
        scan_range_spin = ttk.Spinbox(scan_frame, from_=0.1, to=100, increment=0.1,
                                     textvariable=self.scan_range_var, width=10)
        scan_range_spin.pack(fill=tk.X, padx=5, pady=2)
        self.scan_range_var.trace('w', lambda *args: setattr(self, 'scan_range', self.scan_range_var.get()))
        ttk.Label(scan_frame, text="扫描微调:").pack(anchor=tk.W, padx=5)
        self.scan_fine_var = tk.DoubleVar(value=1.0)
        scan_fine_spin = ttk.Spinbox(scan_frame, from_=0.8, to=1.2, increment=0.01,
                                    textvariable=self.scan_fine_var, width=10)
        scan_fine_spin.pack(fill=tk.X, padx=5, pady=2)
        self.scan_fine_var.trace('w', lambda *args: setattr(self, 'scan_fine', self.scan_fine_var.get()))

        hardware_frame = ttk.LabelFrame(control_frame, text="硬件控制")
        hardware_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(hardware_frame, text="水平时基:").pack(anchor=tk.W, padx=5)
        self.time_base_var = tk.DoubleVar(value=1.0)
        time_base_spin = ttk.Spinbox(hardware_frame, from_=0.00001, to=1000000, increment=0.1,
                                    textvariable=self.time_base_var, width=10)
        time_base_spin.pack(fill=tk.X, padx=5, pady=2)
        self.time_base_var.trace('w', lambda *args: setattr(self, 'time_base', self.time_base_var.get()))
        ttk.Label(hardware_frame, text="垂直时基:").pack(anchor=tk.W, padx=5)
        self.volt_base_var = tk.DoubleVar(value=1.0)
        volt_base_spin = ttk.Spinbox(hardware_frame, from_=0.001, to=10.0, increment=0.001,
                                    textvariable=self.volt_base_var, width=10)
        volt_base_spin.pack(fill=tk.X, padx=5, pady=2)
        self.volt_base_var.trace('w', lambda *args: self.update_volt_per_div(self.volt_base_var.get()))
        ttk.Label(hardware_frame, text="Y轴调整 (V):").pack(anchor=tk.W, padx=5)
        self.y_position_var = tk.DoubleVar(value=0.0)
        y_position_spin = ttk.Spinbox(hardware_frame, from_=-5.0, to=5.0, increment=0.1,
                                     textvariable=self.y_position_var, width=10)
        y_position_spin.pack(fill=tk.X, padx=5, pady=2)
        self.y_position_var.trace('w', lambda *args: setattr(self, 'y_axis_position', self.y_position_var.get()))

        # ========== 新增 X轴调整 ==========
        xscale_frame = ttk.LabelFrame(control_frame, text="X轴调整 (软件)")
        xscale_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(xscale_frame, text="水平缩放:").pack(anchor=tk.W, padx=5)
        self.x_scale_var = tk.DoubleVar(value=1.0)
        x_scale_spin = ttk.Spinbox(xscale_frame, from_=0.1, to=10.0, increment=0.1,
                                   textvariable=self.x_scale_var, width=10)
        x_scale_spin.pack(fill=tk.X, padx=5, pady=2)
        self.x_scale_var.trace('w', lambda *args: setattr(self, 'x_scale', self.x_scale_var.get()))

        cal_frame = ttk.LabelFrame(control_frame, text="校准")
        cal_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(cal_frame, text="自动归零 (校准)", command=self.auto_zero).pack(fill=tk.X, pady=2)

        trig_frame = ttk.LabelFrame(control_frame, text="触发设置")
        trig_frame.pack(fill=tk.X, padx=5, pady=5)
        self.trig_level_var = tk.DoubleVar(value=2.5)
        ttk.Label(trig_frame, text="触发电平 (V):").pack(anchor=tk.W, padx=5)
        trig_spin = ttk.Spinbox(trig_frame, from_=0, to=5, increment=0.1,
                               textvariable=self.trig_level_var, width=10)
        trig_spin.pack(fill=tk.X, padx=5, pady=2)
        self.trig_level_var.trace('w', lambda *args: setattr(self, 'trigger_level', self.trig_level_var.get()))

        for i in range(3):
            ch_frame = ttk.LabelFrame(control_frame, text=f"通道 {i+1} (A{i})")
            ch_frame.pack(fill=tk.X, padx=5, pady=5)
            enable_var = tk.BooleanVar(value=True)
            enable_cb = ttk.Checkbutton(ch_frame, text="启用", variable=enable_var)
            enable_cb.pack(anchor=tk.W, padx=5)
            setattr(self, f'ch{i}_enabled', enable_var)

        xy_frame = ttk.LabelFrame(control_frame, text="XY模式设置")
        xy_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(xy_frame, text="X轴通道:").pack(anchor=tk.W, padx=5)
        self.xy_x_var = tk.StringVar(value="CH1")
        xy_x_combo = ttk.Combobox(xy_frame, textvariable=self.xy_x_var,
                                 values=["CH1", "CH2", "CH3"], state="readonly")
        xy_x_combo.pack(fill=tk.X, padx=5, pady=2)
        xy_x_combo.bind('<<ComboboxSelected>>', self.update_xy_channels)
        ttk.Label(xy_frame, text="Y轴通道:").pack(anchor=tk.W, padx=5)
        self.xy_y_var = tk.StringVar(value="CH2")
        xy_y_combo = ttk.Combobox(xy_frame, textvariable=self.xy_y_var,
                                 values=["CH1", "CH2", "CH3"], state="readonly")
        xy_y_combo.pack(fill=tk.X, padx=5, pady=2)
        xy_y_combo.bind('<<ComboboxSelected>>', self.update_xy_channels)

        btn_frame2 = ttk.Frame(control_frame)
        btn_frame2.pack(fill=tk.X, padx=5, pady=5)
        self.run_btn = ttk.Button(btn_frame2, text="开始采集", command=self.toggle_run)
        self.run_btn.pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="XY模式", command=self.toggle_xy_mode).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="历史回放", command=self.show_history).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="光标测量", command=self.toggle_cursor).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="自动设置", command=self.auto_scale).pack(fill=tk.X, pady=2)
        # ========== 新增按钮 ==========
        ttk.Button(btn_frame2, text="暂停", command=self.pause_acquisition).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame2, text="抓取波形 (Single)", command=self.single_acquisition).pack(fill=tk.X, pady=2)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(right_frame, bg='black', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        self.canvas.bind('<Button-1>', self.on_canvas_click)

        bottom_frame = ttk.Frame(right_frame, height=220)
        bottom_frame.pack(fill=tk.X, pady=(5,0))
        bottom_frame.pack_propagate(False)

        freq_frame = ttk.LabelFrame(bottom_frame, text="实时 & 平均频率/电压")
        freq_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        self.freq_text = tk.Text(freq_frame, height=14, bg='black', fg='white', font=('Consolas', 9))
        self.freq_text.pack(fill=tk.BOTH, expand=True)

        measure_frame = ttk.LabelFrame(bottom_frame, text="自动测量")
        measure_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.measure_text = tk.Text(measure_frame, height=14, bg='black', fg='white', font=('Consolas', 9))
        self.measure_text.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="就绪 | 终极增强版示波器")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def open_settings(self):
        SettingsDialog(self.root, self)

    def update_volt_per_div(self, value):
        for i in range(3):
            self.volt_per_div[i] = value

    def update_xy_channels(self, event=None):
        x_map = {"CH1": 0, "CH2": 1, "CH3": 2}
        y_map = {"CH1": 0, "CH2": 1, "CH3": 2}
        self.xy_ch_x = x_map[self.xy_x_var.get()]
        self.xy_ch_y = y_map[self.xy_y_var.get()]

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
            self.status_var.set(f"✅ 已连接: {port} | 终极示波器就绪")
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
            messagebox.showinfo("光标测量", "左键点击设置光标\n显示ΔT/ΔV测量值")
            self.cursor_t1 = None
            self.cursor_t2 = None

    def toggle_xy_mode(self):
        self.xy_mode = not self.xy_mode
        if self.xy_mode:
            messagebox.showinfo("XY模式", f"XY模式已启用\nX: {self.xy_x_var.get()} | Y: {self.xy_y_var.get()}")
        else:
            messagebox.showinfo("XY模式", "XY模式已禁用")

    def on_canvas_resize(self, event):
        if event.widget == self.canvas:
            self.update_plot()

    def on_canvas_click(self, event):
        if not self.cursor_mode or not self.is_running:
            return
        canvas_width = self.canvas.winfo_width()
        if canvas_width <= 0:
            return
        actual_time_per_div = self.time_base  # ✅ 使用硬件时基
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

    # ========== 新增方法 ==========
    def pause_acquisition(self):
        if self.acq_mode == "PAUSE":
            self.acq_mode = "RUN"
            self.status_var.set("▶ 继续采集")
        else:
            self.acq_mode = "PAUSE"
            self.status_var.set("⏸ 已暂停")
        self.update_plot()

    def single_acquisition(self):
        self.acq_mode = "SINGLE"
        self.single_triggered = False
        self.status_var.set("🎯 等待触发...")

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.root.attributes('-fullscreen', self.fullscreen)

    def exit_fullscreen(self, event=None):
        self.fullscreen = False
        self.root.attributes('-fullscreen', False)

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
                        self.current_data[ch][i] = min(5.0, max(0.0, voltage - self.dc_offset[ch]))
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
        try:
            pot1_raw = data[0] + (data[1] << 8)   # A3: 水平时基
            pot2_raw = data[2] + (data[3] << 8)   # A4: 垂直时基
            pot3_raw = data[4] + (data[5] << 8)   # A5: Y轴调整
            if pot1_raw <= 1:
                self.time_base = 0.00001
            else:
                ratio = pot1_raw / 1023.0
                log_min = math.log10(0.00001)
                log_max = math.log10(1000000.0)
                self.time_base = 10 ** (log_min + ratio * (log_max - log_min))
                self.time_base = max(0.00001, min(1000000.0, self.time_base))
            if pot2_raw <= 1:
                volt_div = 0.001
            else:
                ratio = pot2_raw / 1023.0
                log_min = math.log10(0.001)
                log_max = math.log10(10.0)
                volt_div = 10 ** (log_min + ratio * (log_max - log_min))
                volt_div = max(0.001, min(10.0, volt_div))
            for i in range(3):
                self.volt_per_div[i] = volt_div
            self.y_axis_position = (pot3_raw / 1023.0) * 10.0 - 5.0
            self.time_base_var.set(self.time_base)
            self.volt_base_var.set(volt_div)
            self.y_position_var.set(round(self.y_axis_position, 2))
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
                self.toggle_xy_mode()
            elif btn == 7:  # D9: History Playback
                self.show_history()
            elif btn == 8:  # D10: Cursor
                self.toggle_cursor()
            elif btn == 9:  # D11: Auto Zero
                self.auto_zero()

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
                    volt_div = max(0.001, vpp / 4.0)
                    self.volt_base_var.set(volt_div)
                    self.update_volt_per_div(volt_div)
        messagebox.showinfo("自动设置", "已优化显示参数！")

    def auto_zero(self):
        if not self.is_running:
            messagebox.showwarning("警告", "请先开始采集！")
            return
        for ch in range(3):
            if getattr(self, f'ch{ch}_enabled').get():
                data = self.current_data[ch]
                dc_avg = sum(data) / len(data)
                self.dc_offset[ch] = dc_avg
                print(f"通道 {ch+1} DC偏移校准: {dc_avg:.4f}V")
        self.save_config()
        messagebox.showinfo("自动归零", "DC偏移校准完成！\n已保存校准值。")

    # ========== 频率/电压计算 ==========
    def calculate_frequency_voltage(self):
        for ch in range(3):
            if getattr(self, f'ch{ch}_enabled').get():
                data = self.current_data[ch]
                n = len(data)
                if n > 0:
                    self.channel_voltages[ch] = data[-1]
                    avg_voltage = sum(data) / n
                    self.average_voltages[ch] = avg_voltage
                    freq = self.calculate_frequency(data)
                    self.channel_frequencies[ch] = freq
                    self.frequency_history[ch].append(freq)
                    self.voltage_history[ch].append(avg_voltage)
                    if len(self.frequency_history[ch]) > 10:
                        self.frequency_history[ch].pop(0)
                    if len(self.voltage_history[ch]) > 10:
                        self.voltage_history[ch].pop(0)
                    if self.frequency_history[ch]:
                        self.average_frequencies[ch] = sum(self.frequency_history[ch]) / len(self.frequency_history[ch])
                    if self.voltage_history[ch]:
                        self.average_voltages[ch] = sum(self.voltage_history[ch]) / len(self.voltage_history[ch])
            else:
                self.channel_frequencies[ch] = 0.0
                self.average_frequencies[ch] = 0.0
                self.channel_voltages[ch] = 0.0
                self.average_voltages[ch] = 0.0

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
        return self.sample_rate / avg_period_samples

    # ========== 自动测量 ==========
    def calculate_measurements(self):
        for ch in range(3):
            if getattr(self, f'ch{ch}_enabled').get():
                data = self.current_data[ch]
                n = len(data)
                if n > 0:
                    vmax = max(data)
                    vmin = min(data)
                    vpp = vmax - vmin
                    vavg = sum(data) / n
                    vrms = math.sqrt(sum(x*x for x in data) / n)
                    frequency = self.calculate_frequency(data)
                    period = 1000.0 / frequency if frequency > 0 else 0
                    rise_time = self.calculate_rise_time(data)
                    self.measurements['vpp'][ch] = vpp
                    self.measurements['vmax'][ch] = vmax
                    self.measurements['vmin'][ch] = vmin
                    self.measurements['vavg'][ch] = vavg
                    self.measurements['vrms'][ch] = vrms
                    self.measurements['frequency'][ch] = frequency
                    self.measurements['period'][ch] = period
                    self.measurements['rise_time'][ch] = rise_time
            else:
                for key in self.measurements:
                    self.measurements[key][ch] = 0.0

    def calculate_rise_time(self, data):
        if len(data) < 2:
            return 0.0
        vmin = min(data)
        vmax = max(data)
        vrange = vmax - vmin
        if vrange <= 0:
            return 0.0
        v10 = vmin + 0.1 * vrange
        v90 = vmin + 0.9 * vrange
        t10 = t90 = -1
        for i in range(len(data)):
            if data[i] >= v10 and t10 == -1:
                t10 = i
            if data[i] >= v90 and t90 == -1:
                t90 = i
                break
        if t10 != -1 and t90 != -1 and t90 > t10:
            time_diff = (t90 - t10) / self.sample_rate
            return time_diff * 1000000
        return 0.0

    # ========== 显示系统 ==========
    def update_all_displays(self):
        if self.acq_mode == "PAUSE":
            self.update_plot()
            self.update_frequency_display()
            self.update_measurements_display()
            self.update_status()
            return
        if self.acq_mode == "SINGLE" and not self.single_triggered:
            ch0_data = self.current_data[0]
            if len(ch0_data) > 10:
                for i in range(1, len(ch0_data)):
                    if ch0_data[i-1] < self.trigger_level <= ch0_data[i]:
                        self.single_triggered = True
                        self.acq_mode = "PAUSE"
                        self.status_var.set("✅ 单次触发完成！")
                        break

        self.calculate_frequency_voltage()
        self.calculate_measurements()
        if self.xy_mode:
            self.update_xy_plot()
        else:
            self.update_plot()
        self.update_frequency_display()
        self.update_measurements_display()
        self.update_status()

    def update_plot(self):
        """主波形显示 - 使用硬件控制的 time_base 和 volt_per_div + X轴缩放"""
        try:
            canvas = self.canvas
            canvas.delete("all")
            width = canvas.winfo_width()
            height = canvas.winfo_height()
            if width < 100 or height < 100:
                return

            actual_time_per_div = self.time_base  # ✅ 使用硬件时基
            total_time = actual_time_per_div * 10
            y_min, y_max = -5.0, 10.0
            y_range = y_max - y_min

            # 绘制网格
            grid_steps = {'sparse': 5, 'normal': 10, 'dense': 20}[self.config.get('grid_density', 'normal')]
            for i in range(grid_steps + 1):
                x = (i / grid_steps) * width
                canvas.create_line(x, 0, x, height, fill='#333333')
                if i % (grid_steps // 5) == 0:
                    time_val = i * actual_time_per_div / grid_steps
                    time_label = self.format_time_unit(time_val)
                    canvas.create_text(x, height-15, text=time_label, fill='white', font=('Arial', 8))
            for i in range(16):
                y_val = y_min + i * 1.0
                if y_min <= y_val <= y_max:
                    y = height - ((y_val - y_min) / y_range) * height
                    canvas.create_line(0, y, width, y, fill='#333333')
                    canvas.create_text(10, y, text=f"{y_val:.1f}", fill='white', font=('Arial', 8), anchor='w')

            # 绘制波形
            colors = [self.config.get(f'color_ch{i}', ['cyan', 'yellow', 'magenta'][i]) for i in range(3)]
            for ch in range(3):
                if getattr(self, f'ch{ch}_enabled').get():
                    points = []
                    for i in range(self.SAMPLES_PER_CHAN):
                        normalized_i = i / (self.SAMPLES_PER_CHAN - 1)
                        scaled_i = 0.5 + (normalized_i - 0.5) * self.x_scale
                        x = max(0, min(width, scaled_i * width))
                        voltage_raw = self.current_data[ch][i] + self.y_axis_position
                        voltage_in_divs = voltage_raw / self.volt_per_div[ch]
                        voltage = voltage_in_divs
                        y = height - ((voltage - y_min) / y_range) * height
                        points.extend([x, y])
                    if len(points) >= 4:
                        canvas.create_line(points, fill=colors[ch], width=2)

            # ========== 参考波形 ==========
            if self.config.get('show_reference') and self.reference_waveform:
                ref_color = 'green'
                for ch in range(3):
                    if getattr(self, f'ch{ch}_enabled').get():
                        points = []
                        for i in range(self.SAMPLES_PER_CHAN):
                            normalized_i = i / (self.SAMPLES_PER_CHAN - 1)
                            scaled_i = 0.5 + (normalized_i - 0.5) * self.x_scale
                            x = max(0, min(width, scaled_i * width))
                            voltage_raw = self.reference_waveform[ch][i] + self.y_axis_position
                            voltage_in_divs = voltage_raw / self.volt_per_div[ch]
                            y = height - ((voltage_in_divs - y_min) / y_range) * height
                            points.extend([x, y])
                        if len(points) >= 4:
                            canvas.create_line(points, fill=ref_color, dash=(3, 3), width=1)

            # 触发线
            trigger_voltage_in_divs = (self.trigger_level + self.y_axis_position) / self.volt_per_div[0]
            trigger_y = height - ((trigger_voltage_in_divs - y_min) / y_range) * height
            canvas.create_line(0, trigger_y, width, trigger_y, fill='red', dash=(4, 4))

            # 光标
            if self.cursor_t1 is not None:
                x1 = (self.cursor_t1 / total_time) * width
                canvas.create_line(x1, 0, x1, height, fill='white', dash=(2, 2))
                if self.cursor_t2 is not None:
                    x2 = (self.cursor_t2 / total_time) * width
                    canvas.create_line(x2, 0, x2, height, fill='white', dash=(2, 2))
                    dt = abs(self.cursor_t2 - self.cursor_t1)
                    dt_label = self.format_time_unit(dt)
                    canvas.create_text((x1 + x2) / 2, 20, text=f"ΔT={dt_label}", fill='white')

            # 标题
            title = f"扫描: {self.format_time_unit(actual_time_per_div)}/div | 垂直: {self.volt_per_div[0]:.3f}V/div | X缩放: {self.x_scale:.1f}x"
            canvas.create_text(10, 10, text=title, fill='cyan', anchor='nw')
        except Exception as e:
            print(f"绘图错误: {e}")

    def update_xy_plot(self):
        try:
            canvas = self.canvas
            canvas.delete("all")
            width = canvas.winfo_width()
            height = canvas.winfo_height()
            if width < 100 or height < 100:
                return
            x_data = self.current_data[self.xy_ch_x]
            y_data = self.current_data[self.xy_ch_y]
            points = []
            for i in range(min(len(x_data), len(y_data))):
                x = ((x_data[i] + self.y_axis_position) / 15.0) * width
                y = height - ((y_data[i] + self.y_axis_position) / 15.0) * height
                points.extend([x, y])
            if len(points) >= 4:
                canvas.create_line(points, fill='cyan', width=2)
            x_freq = self.calculate_frequency(x_data)
            y_freq = self.calculate_frequency(y_data)
            x_volt = sum(x_data) / len(x_data) if x_data else 0
            y_volt = sum(y_data) / len(y_data) if y_data else 0
            xy_info = f"XY模式: {['CH1','CH2','CH3'][self.xy_ch_x]} vs {['CH1','CH2','CH3'][self.xy_ch_y]}\n"
            xy_info += f"X频率: {x_freq:.2f}Hz | X电压: {x_volt:.3f}V\n"
            xy_info += f"Y频率: {y_freq:.2f}Hz | Y电压: {y_volt:.3f}V"
            canvas.create_text(10, 10, text=xy_info, fill='cyan', anchor='nw', font=('Arial', 10))
        except Exception as e:
            print(f"XY绘图错误: {e}")

    def format_time_unit(self, time_val):
        if time_val >= 1:
            return f"{time_val:.2f}s" if time_val >= 10 else f"{time_val:.3f}s"
        elif time_val >= 0.001:
            return f"{time_val*1000:.2f}ms"
        elif time_val >= 0.000001:
            return f"{time_val*1000000:.1f}μs"
        else:
            return f"{time_val*1000000000:.0f}ns"

    def update_frequency_display(self):
        try:
            self.freq_text.delete(1.0, tk.END)
            self.freq_text.insert(tk.END, "📊 实时 & 平均频率/电压:\n")
            for ch in range(3):
                if getattr(self, f'ch{ch}_enabled').get():
                    real_freq = self.channel_frequencies[ch]
                    avg_freq = self.average_frequencies[ch]
                    real_volt = self.channel_voltages[ch]
                    avg_volt = self.average_voltages[ch]
                    self.freq_text.insert(tk.END, f"■ 通道 {ch+1} (A{ch}):\n")
                    self.freq_text.insert(tk.END, f"  实时频率: {real_freq:.2f} Hz\n")
                    self.freq_text.insert(tk.END, f"  平均频率: {avg_freq:.2f} Hz\n")
                    self.freq_text.insert(tk.END, f"  实时电压: {real_volt:.4f} V\n")
                    self.freq_text.insert(tk.END, f"  平均电压: {avg_volt:.4f} V\n")
                else:
                    self.freq_text.insert(tk.END, f"■ 通道 {ch+1} (A{ch}): 禁用\n")
        except Exception as e:
            print(f"频率显示错误: {e}")

    def update_measurements_display(self):
        try:
            self.measure_text.delete(1.0, tk.END)
            self.measure_text.insert(tk.END, "📈 自动测量结果:\n")
            for ch in range(3):
                if getattr(self, f'ch{ch}_enabled').get():
                    self.measure_text.insert(tk.END, f"■ 通道 {ch+1} (A{ch}):\n")
                    vpp = self.measurements['vpp'][ch]
                    vmax = self.measurements['vmax'][ch]
                    vmin = self.measurements['vmin'][ch]
                    vavg = self.measurements['vavg'][ch]
                    vrms = self.measurements['vrms'][ch]
                    self.measure_text.insert(tk.END, f"  Vpp:    {vpp:.4f} V\n")
                    self.measure_text.insert(tk.END, f"  Vmax:   {vmax:.4f} V\n")
                    self.measure_text.insert(tk.END, f"  Vmin:   {vmin:.4f} V\n")
                    self.measure_text.insert(tk.END, f"  Vavg:   {vavg:.4f} V\n")
                    self.measure_text.insert(tk.END, f"  Vrms:   {vrms:.4f} V\n")
                    freq = self.measurements['frequency'][ch]
                    period = self.measurements['period'][ch]
                    self.measure_text.insert(tk.END, f"  频率:   {freq:.2f} Hz\n")
                    self.measure_text.insert(tk.END, f"  周期:   {period:.2f} ms\n")
                    rise_time = self.measurements['rise_time'][ch]
                    if rise_time > 0:
                        if rise_time >= 1000:
                            rt_label = f"{rise_time/1000:.2f}ms"
                        else:
                            rt_label = f"{rise_time:.1f}μs"
                        self.measure_text.insert(tk.END, f"  上升时间: {rt_label}\n")
                    self.measure_text.insert(tk.END, "\n")
                else:
                    self.measure_text.insert(tk.END, f"■ 通道 {ch+1} (A{ch}): 禁用\n")
        except Exception as e:
            print(f"测量显示错误: {e}")

    def update_status(self):
        actual_time_per_div = self.scan_range * self.scan_fine
        time_str = self.format_time_unit(actual_time_per_div)
        volt_str = f"{self.volt_per_div[0]:.3f}V/div"
        mode_str = {"RUN": "运行", "PAUSE": "暂停", "SINGLE": "单次"}[self.acq_mode]
        self.status_var.set(f"[{mode_str}] 扫描: {time_str} | 垂直: {volt_str} | X缩放: {self.x_scale:.1f}x | FPS: {self.fps:.1f}")

    def show_xy(self):
        self.toggle_xy_mode()

    def show_history(self):
        if not self.history:
            messagebox.showwarning("警告", "无历史数据！")
            return
        hist_window = tk.Toplevel(self.root)
        hist_window.title("历史回放")
        hist_window.geometry("1000x600")
        canvas = tk.Canvas(hist_window, bg='black')
        canvas.pack(fill=tk.BOTH, expand=True)

    def show_measurements(self):
        self.update_measurements_display()

    def save_data(self):
        if not self.is_running:
            messagebox.showwarning("警告", "请先开始采集！")
            return
        filename = filedialog.asksaveasfilename(defaultextension=f".{self.config.get('export_format', 'csv')}")
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("Time,CH1,CH2,CH3\n")
                    actual_time_per_div = self.time_base
                    total_time = actual_time_per_div * 10
                    for i in range(self.SAMPLES_PER_CHAN):
                        t = i * (total_time / self.SAMPLES_PER_CHAN)
                        f.write(f"{t:.9f},{self.current_data[0][i]:.4f},{self.current_data[1][i]:.4f},{self.current_data[2][i]:.4f}\n")
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
    app = UltimateOscilloscopeFinal(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()