import os
import fitz  # PyMuPDF
from utils import save_pdf_optimized
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from settings_manager import SettingsManager

# ==============================================================================
# 配置
# ==============================================================================
from config import MergerConfig as Config

# ==============================================================================
# 后端逻辑
# ==============================================================================
class MergerBackend:
    def __init__(self):
        self.file_list = []

    def add_files(self, paths):
        count = 0
        existing_paths = {item['path'] for item in self.file_list}
        
        for path in paths:
            if not path.lower().endswith('.pdf'): continue
            if path in existing_paths: continue 
            
            try:
                with fitz.open(path) as doc:
                    pages = doc.page_count
                    
                self.file_list.append({
                    'path': path,
                    'name': os.path.basename(path),
                    'pages': pages
                })
                count += 1
            except:
                print(f"无法读取: {path}")
        return count

    def move_item(self, from_index, to_index):
        if from_index == to_index: return False
        if not (0 <= from_index < len(self.file_list) and 0 <= to_index < len(self.file_list)):
            return False
            
        item = self.file_list.pop(from_index)
        self.file_list.insert(to_index, item)
        return True

    def remove_item(self, index):
        if 0 <= index < len(self.file_list):
            self.file_list.pop(index)

    def clear_all(self):
        self.file_list = []


    def merge(self, save_path):
        if not self.file_list: return
        merged_doc = fitz.open()
        try:
            for item in self.file_list:
                with fitz.open(item['path']) as src_doc:
                    merged_doc.insert_pdf(src_doc)
            
            success = save_pdf_optimized(merged_doc, save_path)
            merged_doc.close()
            return success
        except Exception as e:
            print(f"Merge Error: {e}")
            return False

# ==============================================================================
# UI 组件：可拖拽的文件条目 (修复了事件捕获问题)
# ==============================================================================
class FileItem(ctk.CTkFrame):
    def __init__(self, master, index, file_info, callbacks):
        super().__init__(master, fg_color=("gray95", "gray25"), corner_radius=6, height=40)
        
        self.current_index = index 
        self.callbacks = callbacks 
        
        self.grid_propagate(False) 

        # 1. 拖拽手柄 (≡)
        # width 参数必须在构造函数中指定
        self.lbl_handle = ctk.CTkLabel(self, text="≡", width=40, font=("Arial", 16), cursor="hand2", text_color="gray")
        self.lbl_handle.place(relx=0.0, rely=0, relheight=1)
        
        # 绑定事件
        self.lbl_handle.bind("<Button-1>", self.on_drag_start)
        self.lbl_handle.bind("<B1-Motion>", self.on_drag_motion)
        self.lbl_handle.bind("<ButtonRelease-1>", self.on_drag_end)

        # 2. 序号
        self.lbl_idx = ctk.CTkLabel(self, text=f"{index+1}.", width=30, font=("Arial", 12, "bold"))
        self.lbl_idx.place(x=40, rely=0.25)

        # 3. 文件名
        self.lbl_name = ctk.CTkLabel(self, text=file_info['name'], anchor="w", font=("Microsoft YaHei UI", 13))
        self.lbl_name.place(x=80, rely=0, relheight=1, relwidth=0.6)

        # 4. 页数
        self.lbl_pages = ctk.CTkLabel(self, text=f"{file_info['pages']} 页", width=60, text_color="gray")
        self.lbl_pages.place(relx=0.75, rely=0.25)

        # 5. 删除按钮
        self.btn_del = ctk.CTkButton(self, text="✕", width=30, height=24, fg_color="#dc3545", 
                                     command=lambda: callbacks['remove'](self))
        self.btn_del.place(relx=0.92, rely=0.2)

    def update_index_display(self, new_index):
        self.current_index = new_index
        self.lbl_idx.configure(text=f"{new_index+1}.")

    def set_highlight(self, active):
        if active:
            self.configure(fg_color=("gray85", "gray35"), border_width=2, border_color="#3B8ED0")
        else:
            self.configure(fg_color=("gray95", "gray25"), border_width=0)

    # --- 核心拖拽逻辑修正 ---
    def on_drag_start(self, event):
        self.configure(fg_color="#E1F2F8")
        self.callbacks['drag_start'](self)

    def on_drag_motion(self, event):
        """
        关键修复：
        主动检测鼠标下的组件，因为拖拽时鼠标事件被锁定在当前组件，
        其他组件收不到 Enter 事件，必须手动计算。
        """
        # 1. 获取屏幕绝对坐标
        x, y = self.winfo_pointerxy()
        
        # 2. 找到该坐标下的组件
        target = self.winfo_containing(x, y)
        
        # 3. 向上遍历，直到找到 FileItem
        target_item = None
        while target:
            if isinstance(target, FileItem):
                target_item = target
                break
            if target == self.master: # 到了容器层还没找到，就退出
                break
            try:
                target = target.master
            except:
                break
        
        # 4. 如果找到了目标行，通知 App
        if target_item and target_item != self:
            self.callbacks['drag_enter'](target_item)

    def on_drag_end(self, event):
        self.configure(fg_color=("gray95", "gray25"))
        self.callbacks['drag_end']()

# ==============================================================================
# 主程序
# ==============================================================================

class MergerFrame(ctk.CTkFrame, TkinterDnD.DnDWrapper):
    def __init__(self, master):
        super().__init__(master)
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.backend = MergerBackend()
        self.item_widgets = [] 
        
        self.dragging_item = None 
        self.target_item = None   
        
        self.setup_ui()
        
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.drop_handler)

    def setup_ui(self):
        # self.title(Config.APP_NAME)
        # self.geometry(Config.APP_SIZE)
        # ctk.set_appearance_mode(Config.APPEARANCE_MODE)
        # ctk.set_default_color_theme(Config.THEME_COLOR)

        # 1. Top
        top = ctk.CTkFrame(self, height=60, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(20, 10))
        ctk.CTkLabel(top, text="PDF 合并工坊", font=("Microsoft YaHei UI", 24, "bold")).pack(side="left")
        ctk.CTkLabel(top, text="按住 ≡ 可拖拽排序", text_color="#1F6AA5", font=("", 12)).pack(side="left", padx=15, pady=(10,0))
        ctk.CTkButton(top, text="+ 添加文件", command=self.add_files_dialog, width=100).pack(side="right")

        # 2. List
        self.list_frame = ctk.CTkScrollableFrame(self, label_text="文件列表")
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # 3. Bottom
        bottom = ctk.CTkFrame(self, height=60, fg_color=("gray95", "gray15"))
        bottom.pack(fill="x", side="bottom")
        
        self.lbl_status = ctk.CTkLabel(bottom, text="共 0 个文件", font=("", 13, "bold"))
        self.lbl_status.pack(side="left", padx=20)
        
        ctk.CTkButton(bottom, text="清空", command=self.clear_list, fg_color="transparent", border_width=1, text_color=("gray10", "gray90"), width=60).pack(side="left", padx=10)
        
        self.btn_merge = ctk.CTkButton(bottom, text="开始合并", command=self.merge_files, height=36, width=140, font=("", 15, "bold"), state="disabled")
        self.btn_merge.pack(side="right", padx=20, pady=12)

        self.lbl_empty = ctk.CTkLabel(self.list_frame, text="把 PDF 拖进来\n\n按住 ≡ 拖动可调整顺序", text_color="gray", font=("", 16))
        self.lbl_empty.pack(pady=100)

    # --- 拖拽排序逻辑 ---

    def on_item_drag_start(self, item_widget):
        self.dragging_item = item_widget
        self.configure(cursor="fleur")

    def on_item_drag_enter(self, item_widget):
        # 只有在拖拽状态下才响应
        if not self.dragging_item: return 
        if item_widget == self.dragging_item: return 
        
        # 高亮反馈
        if self.target_item and self.target_item != item_widget:
            self.target_item.set_highlight(False)
            
        self.target_item = item_widget
        self.target_item.set_highlight(True)

    def on_item_drag_end(self):
        self.configure(cursor="")
        
        if self.dragging_item and self.target_item:
            from_idx = self.item_widgets.index(self.dragging_item)
            to_idx = self.item_widgets.index(self.target_item)
            
            # 1. 交换 UI 列表对象
            item = self.item_widgets.pop(from_idx)
            self.item_widgets.insert(to_idx, item)
            
            # 2. 交换后端数据
            self.backend.move_item(from_idx, to_idx)
            
            # 3. 极速重排 (Repack)
            self.repack_list()
            
            # 4. 清理高亮
            self.target_item.set_highlight(False)
        
        self.dragging_item = None
        self.target_item = None

    def repack_list(self):
        if self.lbl_empty: self.lbl_empty.pack_forget()
        
        for i, widget in enumerate(self.item_widgets):
            widget.pack_forget()
            widget.pack(fill="x", padx=5, pady=2)
            widget.update_index_display(i)

    # --- 常规逻辑 ---

    def drop_handler(self, event):
        paths = self.parse_drop_paths(event.data)
        self.add_files(paths)

    def parse_drop_paths(self, data):
        if data.startswith('{') and data.endswith('}'):
            return [p.strip('{}') for p in data.split('} {')]
        return data.split()

    def add_files_dialog(self):
        initial_dir = SettingsManager().get("last_file_directory")
        paths = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")], initialdir=initial_dir)
        if paths: 
            SettingsManager().update_last_dir(paths[0])
            self.add_files(paths)

    def add_files(self, paths):
        added_count = self.backend.add_files(paths)
        if added_count == 0: return

        if self.lbl_empty: self.lbl_empty.destroy()
        self.lbl_empty = None

        start_index = len(self.item_widgets)
        new_items = self.backend.file_list[-added_count:]
        
        callbacks = {
            'remove': self.remove_item_widget,
            'drag_start': self.on_item_drag_start,
            'drag_end': self.on_item_drag_end,
            'drag_enter': self.on_item_drag_enter # 传递这个回调
        }

        for i, info in enumerate(new_items):
            current_idx = start_index + i
            item = FileItem(self.list_frame, current_idx, info, callbacks)
            item.pack(fill="x", padx=5, pady=2)
            self.item_widgets.append(item)

        self.update_status()

    def remove_item_widget(self, widget):
        try:
            idx = self.item_widgets.index(widget)
            self.backend.remove_item(idx)
            widget.destroy()
            self.item_widgets.pop(idx)
            
            for i in range(idx, len(self.item_widgets)):
                self.item_widgets[i].update_index_display(i)
                
            self.update_status()
        except: pass

    def clear_list(self):
        for w in self.item_widgets: w.destroy()
        self.item_widgets = []
        self.backend.clear_all()
        self.update_status()
        
        self.lbl_empty = ctk.CTkLabel(self.list_frame, text="把 PDF 拖进来\n\n按住 ≡ 拖动可调整顺序", text_color="gray", font=("", 16))
        self.lbl_empty.pack(pady=100)

    def update_status(self):
        count = len(self.backend.file_list)
        pages = sum(x['pages'] for x in self.backend.file_list)
        self.lbl_status.configure(text=f"共 {count} 个文件 (合计 {pages} 页)")
        self.btn_merge.configure(state="normal" if count > 0 else "disabled")

    def merge_files(self):
        initial_dir = SettingsManager().get("last_file_directory")
        save_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialdir=initial_dir)
        if not save_path: return
        SettingsManager().update_last_dir(save_path)

        self.btn_merge.configure(state="disabled", text="正在合并...")
        self.update()

        success = self.backend.merge(save_path)
        
        self.btn_merge.configure(state="normal", text="开始合并")
        
        if success:
            size = os.path.getsize(save_path) / (1024*1024)
            messagebox.showinfo("成功", f"合并成功！\n体积: {size:.2f} MB")
        else:
            messagebox.showerror("错误", "合并失败，请检查文件是否被占用")

if __name__ == "__main__":
    from tkinterdnd2 import TkinterDnD
    root = TkinterDnD.Tk()
    root.title(Config.APP_NAME)
    root.geometry(Config.APP_SIZE)
    app = MergerFrame(root)
    app.pack(fill="both", expand=True)
    root.mainloop()