import os
import time
import math
import io
import threading
import multiprocessing
import tempfile
import shutil
from concurrent.futures import ProcessPoolExecutor
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image
import fitz  # PyMuPDF
from natsort import natsorted
from config import Img2PdfConfig as Config
from settings_manager import SettingsManager
from pillow_heif import register_heif_opener

register_heif_opener()

# ==============================================================================
# 配置
# ==============================================================================
from config import Img2PdfConfig as Config
from utils import save_pdf_optimized

# ==============================================================================
# 核心逻辑：通用排版工作单元 (含压缩与自适应)
# ==============================================================================
class PuzzleWorker:
    @staticmethod
    def render_chunk(args):
        image_paths, options, temp_filename = args
        try:
            doc = fitz.open()
            
            # 解析基础参数
            rows = options.get('rows', 1)
            cols = options.get('cols', 1)
            items_per_page = rows * cols
            
            # 压缩参数
            max_dim = options.get('max_dim', 2000)
            quality = options.get('quality', 75)
            
            # 模式判断
            is_standard_mode = (rows == 1 and cols == 1)
            
            total_chunk_imgs = len(image_paths)
            
            for i in range(0, total_chunk_imgs, items_per_page):
                # 获取本页图片
                batch = image_paths[i : i + items_per_page]
                if not batch: break

                # --- 页面尺寸决策 ---
                # 默认根据 options 里的 orientation 设置
                if options['orientation'] == 'l': 
                    pw, ph = Config.A4_H, Config.A4_W
                else: 
                    pw, ph = Config.A4_W, Config.A4_H

                # 【智能优化】标准模式下，根据第一张图自动旋转纸张
                if is_standard_mode and len(batch) == 1:
                    try:
                        with Image.open(batch[0]) as tmp_img:
                            # 如果图片宽>高，且当前纸张是竖向，则转为横向
                            if tmp_img.width > tmp_img.height and pw < ph:
                                pw, ph = ph, pw
                            # 如果图片高>宽，且当前纸张是横向，则转为竖向
                            elif tmp_img.height > tmp_img.width and pw > ph:
                                pw, ph = ph, pw
                    except: pass

                # 创建页面
                page = doc.new_page(width=pw, height=ph)
                
                # 计算格子参数
                valid_w = pw - 2*Config.MARGIN
                valid_h = ph - 2*Config.MARGIN
                cell_w = (valid_w - (cols - 1) * Config.GAP) / cols
                cell_h = (valid_h - (rows - 1) * Config.GAP) / rows

                for j, img_path in enumerate(batch):
                    try:
                        r, c = j // cols, j % cols
                        x0 = Config.MARGIN + c * (cell_w + Config.GAP)
                        y0 = Config.MARGIN + r * (cell_h + Config.GAP)
                        
                        img_area_h = cell_h
                        if options['label_mode'] != 'none': img_area_h -= Config.TEXT_H
                        
                        rect = fitz.Rect(x0, y0, x0 + cell_w, y0 + img_area_h)
                        
                        # --- 图片处理与压缩 ---
                        pil_img = Image.open(img_path)
                        from PIL import ImageOps
                        pil_img = ImageOps.exif_transpose(pil_img)
                        
                        # 核心压缩逻辑：缩放
                        w, h = pil_img.size
                        if w > max_dim or h > max_dim:
                            pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                        
                        # 转字节流 (JPEG压缩)
                        img_byte_arr = io.BytesIO()
                        pil_img.save(img_byte_arr, format='JPEG', quality=quality)
                        
                        # 插入 PDF (居中, 保持比例)
                        page.insert_image(rect, stream=img_byte_arr.getvalue(), keep_proportion=True)
                        
                        # --- 标签 ---
                        if options['label_mode'] != 'none':
                            global_idx = options.get('start_index', 0) + i + j + 1
                            lbl = os.path.basename(img_path) if options['label_mode'] == 'filename' else f"图 {global_idx}"
                            
                            # 文字区域
                            text_rect = fitz.Rect(x0, y0 + img_area_h, x0 + cell_w, y0 + cell_h)
                            
                            # 使用 insert_textbox 自动居中
                            page.insert_textbox(text_rect, lbl, fontname="china-ss", fontsize=10, align=1)
                            
                    except Exception as e:
                        print(f"Skip {img_path}: {e}")
            
            save_pdf_optimized(doc, temp_filename)
            doc.close()
            return temp_filename
        except Exception as e:
            return None

# ==============================================================================
# UI 组件：拖拽条目
# ==============================================================================
class DraggableItem(ctk.CTkFrame):
    def __init__(self, master, index, file_path, callbacks):
        super().__init__(master, fg_color=("gray95", "gray25"), corner_radius=6, height=40)
        self.callbacks = callbacks 
        self.file_path = file_path
        self.grid_propagate(False) 

        self.lbl_handle = ctk.CTkLabel(self, text="≡", width=40, font=("Arial", 16), cursor="hand2", text_color="gray")
        self.lbl_handle.place(relx=0.0, rely=0, relheight=1)
        self.lbl_handle.bind("<Button-1>", self.on_drag_start)
        self.lbl_handle.bind("<B1-Motion>", self.on_drag_motion)
        self.lbl_handle.bind("<ButtonRelease-1>", self.on_drag_end)

        self.lbl_idx = ctk.CTkLabel(self, text=f"{index+1}.", width=30, font=("Arial", 12, "bold"))
        self.lbl_idx.place(x=40, rely=0.25)

        self.lbl_name = ctk.CTkLabel(self, text=os.path.basename(file_path), anchor="w", font=("Microsoft YaHei UI", 13))
        self.lbl_name.place(x=80, rely=0, relheight=1, relwidth=0.8)

        self.btn_del = ctk.CTkButton(self, text="✕", width=30, height=24, fg_color="#dc3545", command=lambda: callbacks['remove'](self))
        self.btn_del.place(relx=0.92, rely=0.2)

    def update_index_display(self, new_index):
        self.lbl_idx.configure(text=f"{new_index+1}.")

    def set_highlight(self, active):
        if active: self.configure(fg_color=("gray85", "gray35"), border_width=2, border_color="#3B8ED0")
        else: self.configure(fg_color=("gray95", "gray25"), border_width=0)

    def on_drag_start(self, event):
        self.configure(fg_color="#E1F2F8")
        self.callbacks['drag_start'](self)

    def on_drag_motion(self, event):
        x, y = self.winfo_pointerxy()
        target = self.winfo_containing(x, y)
        target_item = None
        while target:
            if isinstance(target, DraggableItem): target_item = target; break
            if target == self.master: break
            try: target = target.master
            except: break
        if target_item and target_item != self: self.callbacks['drag_enter'](target_item)

    def on_drag_end(self, event):
        self.configure(fg_color=("gray95", "gray25"))
        self.callbacks['drag_end']()

# ==============================================================================
# 主程序
# ==============================================================================

class Img2PdfFrame(ctk.CTkFrame, TkinterDnD.DnDWrapper):
    def __init__(self, master):
        super().__init__(master)
        self.TkdndVersion = TkinterDnD._require(self)
        
        # self.title(Config.APP_NAME)
        # self.geometry(Config.APP_SIZE)
        # ctk.set_appearance_mode(Config.APPEARANCE_MODE)
        # ctk.set_default_color_theme(Config.THEME_COLOR)
        
        self.item_widgets = [] 
        self.hidden_paths = [] 
        self.dragging_item = None
        self.target_item = None
        self.pending_files = [] 
        self.load_more_btn = None 
        
        self.setup_ui()
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.drop_handler)

    def setup_ui(self):
        self.lbl_title = ctk.CTkLabel(self, text="图片合成 PDF 工具", font=("Microsoft YaHei UI", 24, "bold"))
        self.lbl_title.pack(pady=(20, 5))
        
        self.list_frame = ctk.CTkScrollableFrame(self, label_text="图片列表")
        self.list_frame.pack(pady=5, padx=20, fill="both", expand=True)
        self.lbl_empty = ctk.CTkLabel(self.list_frame, text="请拖入图片...", text_color="gray")
        self.lbl_empty.pack(pady=50)

        self.ctrl_frame = ctk.CTkFrame(self)
        self.ctrl_frame.pack(pady=10, padx=20, fill="x")

        # R1: 控制栏 (稳固布局)
        f_row1 = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        f_row1.pack(fill="x", padx=10, pady=10)
        self.lbl_count = ctk.CTkLabel(f_row1, text="共 0 张", font=("", 14, "bold"), width=80, anchor="w")
        self.lbl_count.pack(side="left")
        ctk.CTkButton(f_row1, text="清空列表", command=self.clear_list, fg_color="red", width=80, height=24).pack(side="left", padx=5)
        ctk.CTkButton(f_row1, text="按文件名排序", command=self.sort_by_name, fg_color="gray", width=100, height=24).pack(side="right")
        self.lbl_loading = ctk.CTkLabel(f_row1, text="", text_color="orange") 
        self.lbl_loading.pack(side="right", padx=20)

        # R2: 模式
        f_row2 = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        f_row2.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(f_row2, text="输出模式:").pack(side="left")
        self.switch_mode = ctk.CTkSwitch(f_row2, text="开启拼图排版 (多合一)", command=self.toggle_puzzle_ui)
        self.switch_mode.pack(side="left", padx=10)

        # R3 Puzzle
        self.frame_puzzle_opts = ctk.CTkFrame(self.ctrl_frame, fg_color=("gray90", "gray20"))
        f_p1 = ctk.CTkFrame(self.frame_puzzle_opts, fg_color="transparent")
        f_p1.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(f_p1, text="网格:").pack(side="left")
        self.entry_rows = ctk.CTkEntry(f_p1, width=40); self.entry_rows.pack(side="left", padx=5); self.entry_rows.insert(0, "2")
        ctk.CTkLabel(f_p1, text="行 x").pack(side="left")
        self.entry_cols = ctk.CTkEntry(f_p1, width=40); self.entry_cols.pack(side="left", padx=5); self.entry_cols.insert(0, "2")
        ctk.CTkLabel(f_p1, text="列 | 纸张:").pack(side="left", padx=(10,5))
        self.seg_orient = ctk.CTkSegmentedButton(f_p1, values=["纵向A4", "横向A4"]); self.seg_orient.pack(side="left"); self.seg_orient.set("纵向A4")
        
        f_p2 = ctk.CTkFrame(self.frame_puzzle_opts, fg_color="transparent")
        f_p2.pack(fill="x", padx=10, pady=(0, 10))
        self.chk_label = ctk.CTkCheckBox(f_p2, text="底部标签", command=self.toggle_label_ui); self.chk_label.pack(side="left")
        self.frame_label_type = ctk.CTkFrame(f_p2, fg_color="transparent")
        self.radio_var = ctk.StringVar(value="filename")
        ctk.CTkRadioButton(self.frame_label_type, text="文件名", variable=self.radio_var, value="filename").pack(side="left", padx=10)
        ctk.CTkRadioButton(self.frame_label_type, text="编号", variable=self.radio_var, value="number").pack(side="left")

        # R4 Standard
        self.frame_std_opts = ctk.CTkFrame(self.ctrl_frame, fg_color="transparent")
        self.frame_std_opts.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(self.frame_std_opts, text="目标总大小(MB):").pack(side="left")
        self.entry_mb = ctk.CTkEntry(self.frame_std_opts, width=60, placeholder_text="50"); self.entry_mb.pack(side="left", padx=5)

        self.btn_run = ctk.CTkButton(self, text="开始导出 PDF", command=self.start_thread, height=50, font=("", 18, "bold"), state="disabled")
        self.btn_run.pack(pady=10, padx=20, fill="x")
        self.progress = ctk.CTkProgressBar(self); self.progress.pack(padx=20, fill="x"); self.progress.set(0)
        self.lbl_status = ctk.CTkLabel(self, text="就绪", text_color="gray"); self.lbl_status.pack(pady=(0, 10))

    # --- UI Toggle ---
    def toggle_puzzle_ui(self):
        if self.switch_mode.get() == 1:
            self.frame_std_opts.pack_forget()
            self.frame_puzzle_opts.pack(fill="x", padx=10, pady=5, after=self.ctrl_frame.winfo_children()[1])
            self.frame_std_opts.pack(fill="x", padx=10, pady=10, after=self.frame_puzzle_opts)
        else:
            self.frame_puzzle_opts.pack_forget()
            self.frame_std_opts.pack(fill="x", padx=10, pady=10)

    def toggle_label_ui(self):
        if self.chk_label.get() == 1: self.frame_label_type.pack(side="left", padx=10)
        else: self.frame_label_type.pack_forget()

    # --- 拖拽排序逻辑 ---
    def on_item_drag_start(self, item_widget):
        self.dragging_item = item_widget
        self.configure(cursor="fleur")

    def on_item_drag_enter(self, item_widget):
        if not self.dragging_item or item_widget == self.dragging_item: return
        if self.target_item and self.target_item != item_widget: self.target_item.set_highlight(False)
        self.target_item = item_widget
        self.target_item.set_highlight(True)

    def on_item_drag_end(self):
        self.configure(cursor="")
        if self.dragging_item and self.target_item:
            from_idx = self.item_widgets.index(self.dragging_item)
            to_idx = self.item_widgets.index(self.target_item)
            item = self.item_widgets.pop(from_idx)
            self.item_widgets.insert(to_idx, item)
            self.repack_list()
            self.target_item.set_highlight(False)
        self.dragging_item = None; self.target_item = None

    def repack_list(self):
        if self.lbl_empty: self.lbl_empty.pack_forget()
        if self.load_more_btn: self.load_more_btn.pack_forget()
        for i, widget in enumerate(self.item_widgets):
            widget.pack_forget()
            widget.pack(fill="x", padx=5, pady=2)
            widget.update_index_display(i)
        if self.hidden_paths and self.load_more_btn:
            self.load_more_btn.pack(fill="x", padx=20, pady=10)

    # --- 懒加载核心 ---
    def drop_handler(self, event):
        data = event.data
        if data.startswith('{') and data.endswith('}'): paths = [p.strip('{}') for p in data.split('} {')]
        else: paths = data.split()
        self.lbl_loading.configure(text="正在扫描...")
        threading.Thread(target=self._scan_files_bg, args=(paths,), daemon=True).start()

    def _scan_files_bg(self, paths):
        valid_ext = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.heic', '.webp')
        new_paths = []
        for p in paths:
            if os.path.isfile(p) and p.lower().endswith(valid_ext): new_paths.append(p)
            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith(valid_ext): new_paths.append(os.path.join(root, f))
        
        sorted_new = natsorted(list(set(new_paths)))
        self.after(0, lambda: self._process_new_files(sorted_new))

    def _process_new_files(self, new_paths):
        if not new_paths: 
            self.lbl_loading.configure(text="")
            return
        if self.lbl_empty: self.lbl_empty.destroy(); self.lbl_empty = None
        
        to_show = []
        to_hide = []
        remaining_slots = max(0, Config.INITIAL_LOAD_COUNT - len(self.item_widgets))
        
        if remaining_slots > 0:
            to_show = new_paths[:remaining_slots]
            to_hide = new_paths[remaining_slots:]
        else:
            to_hide = new_paths
            
        self.hidden_paths.extend(to_hide)
        
        if to_show:
            self.pending_files = to_show
            self._batch_add_step()
        else:
            self.check_load_more_btn() 
            self.update_status()
            self.lbl_loading.configure(text="")

    def _batch_add_step(self):
        batch_size = 20
        current_batch = self.pending_files[:batch_size]
        self.pending_files = self.pending_files[batch_size:]
        
        start_idx = len(self.item_widgets)
        callbacks = {
            'remove': self.remove_item,
            'drag_start': self.on_item_drag_start,
            'drag_end': self.on_item_drag_end,
            'drag_enter': self.on_item_drag_enter
        }
        
        if self.load_more_btn: self.load_more_btn.pack_forget()
        
        for i, path in enumerate(current_batch):
            item = DraggableItem(self.list_frame, start_idx + i, path, callbacks)
            item.pack(fill="x", padx=5, pady=2)
            self.item_widgets.append(item)
            
        self.check_load_more_btn()
        self.update_status()
        
        if self.pending_files:
            self.after(20, self._batch_add_step)
        else:
            self.lbl_loading.configure(text="")

    def check_load_more_btn(self):
        if self.hidden_paths:
            if not self.load_more_btn:
                self.load_more_btn = ctk.CTkButton(self.list_frame, text=f"▼ 加载剩余 {len(self.hidden_paths)} 张图片...", fg_color="gray", command=self.load_all_remaining)
            else:
                self.load_more_btn.configure(text=f"▼ 加载剩余 {len(self.hidden_paths)} 张图片...")
            self.load_more_btn.pack(fill="x", padx=20, pady=10)
        else:
            if self.load_more_btn:
                self.load_more_btn.destroy()
                self.load_more_btn = None

    def load_all_remaining(self):
        self.pending_files = self.hidden_paths
        self.hidden_paths = []
        if self.load_more_btn: self.load_more_btn.destroy(); self.load_more_btn = None
        self._batch_add_step()

    def remove_item(self, widget):
        try:
            idx = self.item_widgets.index(widget)
            widget.destroy()
            self.item_widgets.pop(idx)
            for i in range(idx, len(self.item_widgets)):
                self.item_widgets[i].update_index_display(i)
            self.update_status()
        except: pass

    def clear_list(self):
        for w in self.item_widgets: w.destroy()
        self.item_widgets = []
        self.hidden_paths = []
        if self.load_more_btn: self.load_more_btn.destroy(); self.load_more_btn = None
        self.update_status()
        self.lbl_empty = ctk.CTkLabel(self.list_frame, text="请拖入图片...", text_color="gray")
        self.lbl_empty.pack(pady=50)

    def sort_by_name(self):
        if self.hidden_paths:
            if messagebox.askyesno("提示", "排序需要先加载所有隐藏图片，是否继续？"):
                self.load_all_remaining()
            return
        if not self.item_widgets: return
        zipped = [(w.file_path, w) for w in self.item_widgets]
        zipped_sorted = natsorted(zipped, key=lambda x: x[0])
        self.item_widgets = [x[1] for x in zipped_sorted]
        self.repack_list()

    def update_status(self):
        total = len(self.item_widgets) + len(self.hidden_paths)
        self.lbl_count.configure(text=f"共 {total} 张")
        self.btn_run.configure(state="normal" if total > 0 else "disabled")

    # --- 执行 ---
    def start_thread(self):
        initial_dir = SettingsManager().get("last_file_directory")
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")], initialdir=initial_dir)
        if not save_path: return
        SettingsManager().update_last_dir(save_path)
        
        mode = "puzzle" if self.switch_mode.get() == 1 else "standard"
        opts = {}
        final_image_paths = [w.file_path for w in self.item_widgets] + self.hidden_paths
        
        try: opts['target_mb'] = float(self.entry_mb.get() or 50)
        except: opts['target_mb'] = 50.0
        
        # --- 统一计算压缩参数 ---
        # 无论是拼图还是标准模式，都先算出 "每张图能分到多少KB"
        total_kb = opts['target_mb'] * 1024 * 0.90 # 预留10%
        avg_kb = total_kb / max(1, len(final_image_paths))
        
        # 分级压缩策略 (Granular Compression Scale)
        if avg_kb < 50: opts['max_dim'] = 800; opts['quality'] = 40
        elif avg_kb < 100: opts['max_dim'] = 1000; opts['quality'] = 50
        elif avg_kb < 200: opts['max_dim'] = 1500; opts['quality'] = 65
        elif avg_kb < 500: opts['max_dim'] = 2000; opts['quality'] = 75
        else: opts['max_dim'] = 2500; opts['quality'] = 85
        
        if mode == "puzzle":
            try:
                opts['rows'] = int(self.entry_rows.get())
                opts['cols'] = int(self.entry_cols.get())
                if opts['rows'] < 1 or opts['cols'] < 1: raise ValueError
            except: messagebox.showerror("错误", "行数和列数必须是正整数"); return
            
            opts['orientation'] = 'l' if self.seg_orient.get() == "横向A4" else 'p'
            opts['label_mode'] = self.radio_var.get() if self.chk_label.get() == 1 else 'none'
        else:
            # 标准模式伪装成 1x1 拼图，但 orientation 不强制
            # 我们在 Worker 里处理自适应旋转
            opts['rows'] = 1
            opts['cols'] = 1
            opts['orientation'] = 'p' # 默认纵向，具体由Worker内部自适应
            opts['label_mode'] = 'none'

        self.btn_run.configure(state="disabled", text="正在处理...")
        self.progress.set(0)
        
        threading.Thread(target=self.run_process_multicore, args=(final_image_paths, opts, save_path), daemon=True).start()

    def run_process_multicore(self, image_paths, opts, save_path):
        import time
        t_start = time.time()
        try:
            cpu_count = multiprocessing.cpu_count()
            total_files = len(image_paths)
            if total_files < 10: cpu_count = 1
            
            # 计算切分 (拼图模式必须按页对齐)
            items_per_page = opts['rows'] * opts['cols']
            pages_per_core = math.ceil((total_files / items_per_page) / cpu_count)
            chunk_size = pages_per_core * items_per_page
                
            temp_dir = tempfile.mkdtemp()
            tasks = []
            
            for i in range(0, total_files, chunk_size):
                chunk = image_paths[i : i + chunk_size]
                temp_file = os.path.join(temp_dir, f"part_{len(tasks)}.pdf")
                chunk_opts = opts.copy()
                chunk_opts['start_index'] = i
                tasks.append((chunk, chunk_opts, temp_file))

            processed_pdfs = []
            with ProcessPoolExecutor(max_workers=cpu_count) as executor:
                futures = [executor.submit(PuzzleWorker.render_chunk, t) for t in tasks]
                import concurrent.futures
                completed_count = 0
                for f in concurrent.futures.as_completed(futures):
                    res = f.result()
                    if res: processed_pdfs.append(res)
                    completed_count += 1
                    prog = completed_count / len(tasks)
                    self.after(0, lambda v=prog: [self.progress.set(v), self.lbl_status.configure(text=f"生成中: {int(v*100)}%")])

            self.lbl_status.configure(text="正在合并...")
            final_doc = fitz.open()
            # 按文件名排序 temp files
            processed_pdfs.sort(key=lambda x: int(os.path.basename(x).split('_')[1].split('.')[0]))
            
            for pdf_path in processed_pdfs:
                with fitz.open(pdf_path) as sub: final_doc.insert_pdf(sub)
            
            save_pdf_optimized(final_doc, save_path)
            final_doc.close()
            shutil.rmtree(temp_dir)
            
            size = os.path.getsize(save_path) / (1024*1024)
            duration = time.time() - t_start
            self.after(0, lambda: messagebox.showinfo("成功", f"文件已生成！\n大小: {size:.2f} MB\n耗时: {duration:.2f}s"))
            
        except Exception as e:
            print(e)
            self.after(0, lambda: messagebox.showerror("错误", str(e)))
        finally:
            self.after(0, lambda: [self.btn_run.configure(state="normal", text="开始导出 PDF"), self.lbl_status.configure(text="就绪")])

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from tkinterdnd2 import TkinterDnD
    root = TkinterDnD.Tk()
    root.title(Config.APP_NAME)
    root.geometry(Config.APP_SIZE)
    app = Img2PdfFrame(root)
    app.pack(fill="both", expand=True)
    root.mainloop()