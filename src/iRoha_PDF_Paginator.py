import os
import math
import fitz  # PyMuPDF
import customtkinter as ctk
from tkinter import filedialog, messagebox, Canvas, colorchooser
from tkinterdnd2 import DND_FILES, TkinterDnD
from settings_manager import SettingsManager
import threading

# ==============================================================================
# 配置
# ==============================================================================
from config import PaginatorConfig as Config, GlobalConfig
from utils import save_pdf_optimized

# ==============================================================================
# UI 组件：九宫格
# ==============================================================================
class PositionSelector(ctk.CTkFrame):
    def __init__(self, master, command=None):
        super().__init__(master, fg_color="transparent")
        self.command = command
        self.buttons = {}
        self.current_pos = "bottom-center"
        
        positions = [
            ("top-left", "↖"), ("top-center", "↑"), ("top-right", "↗"),
            ("center-left", "←"), ("center-center", "•"), ("center-right", "→"),
            ("bottom-left", "↙"), ("bottom-center", "↓"), ("bottom-right", "↘")
        ]
        
        for i, (pos, symbol) in enumerate(positions):
            r, c = divmod(i, 3)
            btn = ctk.CTkButton(
                self, text=symbol, width=40, height=40, 
                fg_color="gray80" if pos != self.current_pos else GlobalConfig.THEME_COLOR,
                text_color="gray20" if pos != self.current_pos else "white",
                command=lambda p=pos: self.select(p)
            )
            btn.grid(row=r, column=c, padx=3, pady=3)
            self.buttons[pos] = btn
            
    def select(self, pos, silent=False):
        if self.current_pos in self.buttons:
            old_btn = self.buttons[self.current_pos]
            old_btn.configure(fg_color="gray80", text_color="gray20")
        
        self.current_pos = pos
        new_btn = self.buttons[pos]
        new_btn.configure(fg_color=GlobalConfig.THEME_COLOR, text_color="white")
        
        if self.command and not silent: self.command()

# ==============================================================================
# 主程序
# ==============================================================================

class PaginatorFrame(ctk.CTkFrame, TkinterDnD.DnDWrapper):
    def __init__(self, master):
        super().__init__(master)
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.file_path = None
        self.file_page_count = 0
        
        self.text_color_hex = "#000000"
        self.text_color_rgb = (0, 0, 0)
        
        self.setup_ui()
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.drop_handler)
        
        # 初始化
        self.pos_selector.select("bottom-center", silent=True)
        self.after(200, self.update_preview)

    def setup_ui(self):
        # self.title(Config.APP_NAME)
        # self.geometry(Config.APP_SIZE)
        # ctk.set_appearance_mode(Config.APPEARANCE_MODE)
        # ctk.set_default_color_theme(Config.THEME_COLOR)

        # 1. 顶部
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(fill="x", padx=20, pady=15)
        self.btn_open = ctk.CTkButton(self.frame_top, text="📂 打开 PDF", command=self.open_file, width=120)
        self.btn_open.pack(side="left", padx=15, pady=10)
        self.lbl_file = ctk.CTkLabel(self.frame_top, text="请拖入 PDF 文件", text_color="gray", font=("", 14))
        self.lbl_file.pack(side="left", padx=10)

        # 2. 中间
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        container.pack(fill="both", expand=True)
        
        # === 左侧 ===
        self.frame_left = ctk.CTkFrame(container)
        self.frame_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # 范围
        ctk.CTkLabel(self.frame_left, text="1. 范围", font=("", 14, "bold")).pack(anchor="w", padx=15, pady=(10, 5))
        f_range = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        f_range.pack(fill="x", padx=15)
        self.entry_start = ctk.CTkEntry(f_range, width=60); self.entry_start.pack(side="left", padx=5); self.entry_start.insert(0, "1")
        ctk.CTkLabel(f_range, text="-").pack(side="left")
        self.entry_end = ctk.CTkEntry(f_range, width=60); self.entry_end.pack(side="left", padx=5)

        # 逻辑
        ctk.CTkLabel(self.frame_left, text="2. 逻辑", font=("", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        f_logic = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        f_logic.pack(fill="x", padx=15)
        ctk.CTkLabel(f_logic, text="起始值:").grid(row=0, column=0, padx=5)
        self.entry_logic_start = ctk.CTkEntry(f_logic, width=60); self.entry_logic_start.grid(row=0, column=1); self.entry_logic_start.insert(0, "1")
        ctk.CTkLabel(f_logic, text="总页数:").grid(row=0, column=2, padx=5)
        self.entry_total = ctk.CTkEntry(f_logic, width=60); self.entry_total.grid(row=0, column=3)
        self.chk_auto_total = ctk.CTkCheckBox(f_logic, text="自动", width=60, command=self.toggle_total_entry); self.chk_auto_total.grid(row=0, column=4, padx=5); self.chk_auto_total.select()

        # 样式
        ctk.CTkLabel(self.frame_left, text="3. 样式 & 颜色", font=("", 14, "bold")).pack(anchor="w", padx=15, pady=(15, 5))
        f_style = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        f_style.pack(fill="x", padx=15)
        self.combo_tpl = ctk.CTkComboBox(f_style, values=["{n}", "- {n} -", "{n} / {t}", "第 {n} 页"], width=150, command=self.update_preview)
        self.combo_tpl.grid(row=0, column=0, columnspan=2, pady=5, sticky="w"); self.combo_tpl.set("- {n} -")
        ctk.CTkLabel(f_style, text="字号:").grid(row=1, column=0, sticky="w")
        self.slider_font = ctk.CTkSlider(f_style, from_=6, to=100, number_of_steps=94, command=self.update_preview)
        self.slider_font.grid(row=1, column=1, sticky="ew"); self.slider_font.set(12)

        f_color = ctk.CTkFrame(self.frame_left, fg_color="transparent")
        f_color.pack(fill="x", padx=15, pady=10)
        self.btn_color = ctk.CTkButton(f_color, text="A  字体颜色", width=100, fg_color="black", command=self.pick_color)
        self.btn_color.pack(side="left", padx=5)
        self.chk_bg_box = ctk.CTkCheckBox(f_color, text="加白底 (防深色背景)", command=self.update_preview); self.chk_bg_box.pack(side="left", padx=15)

        # === 右侧 ===
        self.frame_right = ctk.CTkFrame(container)
        self.frame_right.pack(side="right", fill="both", expand=True, padx=(10, 0))
        ctk.CTkLabel(self.frame_right, text="4. 位置微调", font=("", 14, "bold")).pack(anchor="w", padx=15, pady=(10, 5))
        self.pos_selector = PositionSelector(self.frame_right, command=self.update_preview)
        self.pos_selector.pack(pady=5)
        
        f_off = ctk.CTkFrame(self.frame_right, fg_color="transparent"); f_off.pack(pady=5)
        ctk.CTkLabel(f_off, text="X偏移:").pack(side="left"); self.entry_off_x = ctk.CTkEntry(f_off, width=50); self.entry_off_x.pack(side="left"); self.entry_off_x.insert(0, "20")
        ctk.CTkLabel(f_off, text="Y偏移:").pack(side="left", padx=(10,0)); self.entry_off_y = ctk.CTkEntry(f_off, width=50); self.entry_off_y.pack(side="left"); self.entry_off_y.insert(0, "20")

        self.canvas = Canvas(self.frame_right, width=200, height=280, bg="#E0E0E0", highlightthickness=0)
        self.canvas.pack(pady=15)
        self.canvas.create_rectangle(20, 20, 180, 260, fill="white", outline="gray")
        self.preview_bg = self.canvas.create_rectangle(0,0,0,0, fill="white", outline="", state="hidden")
        self.preview_text = self.canvas.create_text(100, 140, text="", font=("Arial", 12))

        # 3. 底部
        self.frame_bot = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_bot.pack(fill="x", side="bottom", padx=20, pady=20)
        self.progress = ctk.CTkProgressBar(self.frame_bot); self.progress.pack(fill="x", pady=(0,10)); self.progress.set(0)
        self.btn_run = ctk.CTkButton(self.frame_bot, text="开始处理 (强力坐标修正)", command=self.start_processing, height=50, font=("", 18, "bold"), state="disabled")
        self.btn_run.pack(fill="x")

        self.bind_events()
        self.toggle_total_entry()

    def bind_events(self):
        for w in [self.entry_start, self.entry_end, self.entry_logic_start, self.entry_total, self.entry_off_x, self.entry_off_y]:
            w.bind("<KeyRelease>", self.update_preview)

    def pick_color(self):
        color = colorchooser.askcolor()
        if color[1]:
            self.text_color_hex = color[1]
            self.text_color_rgb = tuple(map(int, color[0]))
            self.btn_color.configure(fg_color=self.text_color_hex, text_color="white" if sum(self.text_color_rgb)<380 else "black")
            self.update_preview()

    def drop_handler(self, event):
        path = event.data
        if path.startswith('{') and path.endswith('}'): path = path[1:-1]
        if path.lower().endswith('.pdf'): self.load_file(path)

    def open_file(self):
        initial_dir = SettingsManager().get("last_file_directory")
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")], initialdir=initial_dir)
        if path: 
            SettingsManager().update_last_dir(path)
            self.load_file(path)

    def load_file(self, path):
        self.file_path = path
        try:
            with fitz.open(path) as doc:
                self.file_page_count = doc.page_count
            self.lbl_file.configure(text=f"{os.path.basename(path)} ({self.file_page_count}页)", text_color="black")
            self.btn_run.configure(state="normal")
            self.entry_end.delete(0, "end"); self.entry_end.insert(0, str(self.file_page_count))
            if self.chk_auto_total.get(): self.update_total_entry()
            self.update_preview()
        except Exception as e: messagebox.showerror("错误", str(e))

    def toggle_total_entry(self):
        if self.chk_auto_total.get():
            self.entry_total.configure(state="normal")
            self.update_total_entry()
            self.entry_total.configure(state="disabled")
        else: self.entry_total.configure(state="normal")
        self.update_preview()

    def update_total_entry(self):
        try:
            s = int(self.entry_start.get())
            e = int(self.entry_end.get())
            self.entry_total.delete(0, "end"); self.entry_total.insert(0, str(max(0, e-s+1)))
        except: pass

    def update_preview(self, _=None):
        if not hasattr(self, 'pos_selector'): return
        try:
            pos = self.pos_selector.current_pos
            x_off = int(self.entry_off_x.get())
            y_off = int(self.entry_off_y.get())
            font_size = int(self.slider_font.get())
            tpl = self.combo_tpl.get()
            logic_s = self.entry_logic_start.get()
            total_v = self.entry_total.get()
        except: return

        W, H = 160, 240
        sx, sy = 20, 20
        text_str = tpl.replace("{n}", logic_s).replace("{t}", total_v)
        est_w = len(text_str) * (font_size * 0.6)
        est_h = font_size
        
        cx, cy = 0, 0
        anchor = "center"
        if "top" in pos: cy = sy + y_off + est_h/2
        elif "bottom" in pos: cy = sy + H - y_off - est_h/2
        else: cy = sy + H/2 + y_off
        
        if "left" in pos: cx = sx + x_off + est_w/2; anchor = "center" 
        elif "right" in pos: cx = sx + W - x_off - est_w/2; anchor = "center"
        else: cx = sx + W/2 + x_off; anchor = "center"

        if self.chk_bg_box.get():
            self.canvas.coords(self.preview_bg, cx - est_w/2 - 4, cy - est_h/2 - 2, cx + est_w/2 + 4, cy + est_h/2 + 2)
            self.canvas.itemconfig(self.preview_bg, state="normal")
        else:
            self.canvas.itemconfig(self.preview_bg, state="hidden")

        self.canvas.coords(self.preview_text, cx, cy)
        self.canvas.itemconfig(self.preview_text, text=text_str, font=("Arial", int(font_size/1.5)), fill=self.text_color_hex, anchor=anchor)

    def start_processing(self):
        try:
            cfg = {
                'start_p': int(self.entry_start.get()),
                'end_p': int(self.entry_end.get()),
                'logic_s': int(self.entry_logic_start.get()),
                'total': int(self.entry_total.get()),
                'tpl': self.combo_tpl.get(),
                'size': int(self.slider_font.get()),
                'pos': self.pos_selector.current_pos,
                'mx': float(self.entry_off_x.get()),
                'my': float(self.entry_off_y.get()),
                'rgb': self.text_color_rgb,
                'bg_box': self.chk_bg_box.get()
            }
        except: messagebox.showerror("错误", "参数有误"); return

        initial_dir = SettingsManager().get("last_file_directory")
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialdir=initial_dir)
        if not save_path: return
        SettingsManager().update_last_dir(save_path)

        self.btn_run.configure(state="disabled", text="正在处理...")
        self.progress.set(0)
        threading.Thread(target=self.run_worker, args=(cfg, save_path), daemon=True).start()

    def run_worker(self, cfg, save_path):
        """
        【算法核心升级】
        使用 Visual Rect + Derotation Matrix 解决扫描件坐标错位问题
        """
        try:
            doc = fitz.open(self.file_path)
            
            p_start = cfg['start_p'] - 1
            p_end = cfg['end_p'] - 1
            target_pages = range(p_start, min(p_end + 1, len(doc)))
            total_task = len(target_pages)

            if total_task == 0: raise ValueError("范围无效")

            for i, idx in enumerate(target_pages):
                page = doc[idx]
                
                # 1. 修复图层
                try: page.clean_contents()
                except: pass

                # 2. 文本内容
                log_num = (idx - p_start) + cfg['logic_s']
                text = cfg['tpl'].replace("{n}", str(log_num)).replace("{t}", str(cfg['total']))
                
                # 3. 坐标计算（核心！）
                # 获取可见区域 rect (这已经是旋转后的、人眼看到的矩形)
                rect = page.rect
                
                # 获取文本宽度（用于对齐）
                text_len = fitz.get_text_length(text, fontname="helv", fontsize=cfg['size'])
                
                # 在【可视坐标系】中计算目标点 (vx, vy)
                vx, vy = 0, 0
                
                # Y轴 (基线)
                # 注意：insert_text 的锚点是基线左侧
                if "top" in cfg['pos']: vy = rect.y0 + cfg['my'] + cfg['size']
                elif "bottom" in cfg['pos']: vy = rect.y1 - cfg['my']
                else: vy = rect.height/2 + cfg['my'] + cfg['size']/2
                
                # X轴
                if "left" in cfg['pos']: vx = rect.x0 + cfg['mx']
                elif "right" in cfg['pos']: vx = rect.x1 - cfg['mx'] - text_len
                else: vx = rect.x0 + (rect.width/2) + cfg['mx'] - text_len/2

                # 4. 坐标逆向映射 (Visual -> Physical)
                # 将我们在可视区域算好的点，转换回 PDF 物理坐标
                vis_point = fitz.Point(vx, vy)
                # 使用 derotation_matrix 将可视点映射回物理点
                phys_point = vis_point * page.derotation_matrix
                
                # 5. 写入
                # rotate=page.rotation 确保文字跟着页面的旋转方向走，保持“正立”
                
                # 绘制背景块
                if cfg['bg_box']:
                    # 构造一个可视区域的矩形
                    vis_rect = fitz.Rect(vx - 4, vy - cfg['size'] - 2, vx + text_len + 4, vy + 4)
                    # 映射回物理矩形
                    phys_rect = vis_rect * page.derotation_matrix
                    page.draw_rect(phys_rect, color=(1,1,1), fill=(1,1,1), overlay=True)

                page.insert_text(
                    phys_point, # 使用物理坐标
                    text,
                    fontsize=cfg['size'],
                    fontname="helv",
                    color=[c/255 for c in cfg['rgb']],
                    rotate=page.rotation, # 【关键】跟随页面旋转
                    overlay=True
                )
                
                if i % 10 == 0 or i == total_task - 1:
                    self.after(0, lambda v=(i+1)/total_task: self.progress.set(v))

            save_pdf_optimized(doc, save_path)
            doc.close()
            self.after(0, lambda: self.finish(True))
            
        except Exception as e:
            print(e)
            self.after(0, lambda: self.finish(False, str(e)))

    def finish(self, success, msg=""):
        self.progress.stop()
        self.btn_run.configure(state="normal", text="开始处理")
        if success: messagebox.showinfo("完成", "成功！")
        else: messagebox.showerror("错误", f"失败: {msg}")

if __name__ == "__main__":
    from tkinterdnd2 import TkinterDnD
    root = TkinterDnD.Tk()
    root.title(Config.APP_NAME)
    root.geometry(Config.APP_SIZE)
    app = PaginatorFrame(root)
    app.pack(fill="both", expand=True)
    root.mainloop()