import os
import threading
import fitz  # PyMuPDF
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from settings_manager import SettingsManager

# ==============================================================================
# 配置
# ==============================================================================
from config import EditorConfig as Config
from utils import save_pdf_optimized, render_page_to_image

# ==============================================================================
# 后端逻辑
# ==============================================================================

from abc import ABC, abstractmethod
from typing import List, Any

# --- Command Pattern ---
class Command(ABC):
    """Abstract base class for undoable commands."""
    @abstractmethod
    def execute(self) -> None:
        pass
    
    @abstractmethod
    def undo(self) -> None:
        pass

class RotatePageCommand(Command):
    """Command to rotate a page."""
    def __init__(self, backend: 'PDFBackend', current_index: int, angle: int):
        self.backend = backend
        self.current_index = current_index
        self.angle = angle
    
    def execute(self) -> None:
        orig_idx = self.backend.get_original_index(self.current_index)
        if orig_idx == -1: return
        page = self.backend.doc[orig_idx]
        page.set_rotation(page.rotation + self.angle)
    
    def undo(self) -> None:
        orig_idx = self.backend.get_original_index(self.current_index)
        if orig_idx == -1: return
        page = self.backend.doc[orig_idx]
        page.set_rotation(page.rotation - self.angle)

class DeletePageCommand(Command):
    """Command to delete a page (stores mapping for undo)."""
    def __init__(self, backend: 'PDFBackend', current_index: int):
        self.backend = backend
        self.current_index = current_index
        self.deleted_mapping: int = -1  # Store the original page index
    
    def execute(self) -> None:
        if 0 <= self.current_index < len(self.backend.page_mapping):
            self.deleted_mapping = self.backend.page_mapping.pop(self.current_index)
    
    def undo(self) -> None:
        if self.deleted_mapping != -1:
            self.backend.page_mapping.insert(self.current_index, self.deleted_mapping)

# --- Backend ---
class PDFBackend:
    def __init__(self):
        self.doc = None
        self.file_path = None
        self.page_mapping: List[int] = [] 
        self.clipboard: List[int] = []
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []

    def load(self, path: str) -> None:
        self.file_path = path
        self.doc = fitz.open(path)
        self.page_mapping = list(range(len(self.doc)))
        self.undo_stack.clear()
        self.redo_stack.clear()

    def get_page_count(self) -> int:
        return len(self.page_mapping) if self.doc else 0

    def get_original_index(self, current_index: int) -> int:
        if 0 <= current_index < len(self.page_mapping):
            return self.page_mapping[current_index]
        return -1

    def is_landscape(self, current_index: int) -> bool:
        if not self.doc: return False
        try:
            orig_idx = self.get_original_index(current_index)
            page = self.doc[orig_idx]
            rect = page.rect 
            return rect.width > rect.height
        except: return False

    # --- Command Execution ---
    def execute_command(self, cmd: Command) -> None:
        """Execute a command and push to undo stack."""
        cmd.execute()
        self.undo_stack.append(cmd)
        self.redo_stack.clear()  # Clear redo stack on new action

    def undo(self) -> bool:
        """Undo last command. Returns True if successful."""
        if not self.undo_stack:
            return False
        cmd = self.undo_stack.pop()
        cmd.undo()
        self.redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        """Redo last undone command. Returns True if successful."""
        if not self.redo_stack:
            return False
        cmd = self.redo_stack.pop()
        cmd.execute()
        self.undo_stack.append(cmd)
        return True

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    # --- Legacy methods (still used by cut/paste) ---
    def rotate_page(self, current_index: int, angle: int) -> None:
        cmd = RotatePageCommand(self, current_index, angle)
        self.execute_command(cmd)

    def delete_page(self, current_index: int) -> None:
        cmd = DeletePageCommand(self, current_index)
        self.execute_command(cmd)

    def cut_pages(self, current_indices) -> List[int]:
        sorted_indices = sorted(list(current_indices), reverse=True)
        cut_items = []
        for idx in sorted_indices:
            if 0 <= idx < len(self.page_mapping):
                cut_items.append(self.page_mapping.pop(idx))
        return cut_items[::-1]

    def paste_pages(self, target_current_index: int, items: List[int]) -> None:
        for item in reversed(items):
            self.page_mapping.insert(target_current_index, item)

    def save(self, save_path: str) -> None:
        if not self.doc: return
        new_doc = fitz.open()
        for orig_idx in self.page_mapping:
            new_doc.insert_pdf(self.doc, from_page=orig_idx, to_page=orig_idx)
        
        save_pdf_optimized(new_doc, save_path)
        new_doc.close()

    def render_thumbnail(self, orig_idx: int):
        if not self.doc or orig_idx == -1: return None
        return render_page_to_image(self.doc[orig_idx], Config.IMG_MAX_SIZE)


# ==============================================================================
# UI 组件：固定尺寸卡片
# ==============================================================================
class PageCard(ctk.CTkFrame):
    def __init__(self, master, index, backend, select_callback, menu_callback):
        super().__init__(
            master, 
            width=Config.CARD_WIDTH, 
            height=Config.CARD_HEIGHT, 
            fg_color="transparent", 
            corner_radius=8, 
            border_width=0
        )
        
        # 禁止布局传播
        self.grid_propagate(False) 
        
        self.current_index = index 
        self.backend = backend
        self.select_callback = select_callback
        self.menu_callback = menu_callback
        self.is_selected = False

        # 布局
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        
        # 图片 Label
        self.lbl_img = ctk.CTkLabel(self, text="", fg_color="#F0F0F0", corner_radius=4)
        self.lbl_img.grid(row=0, column=0, padx=10, pady=(10, 5))
        
        # 文字 Label
        self.lbl_num = ctk.CTkLabel(self, text="", font=("Arial", 11, "bold"), text_color="gray")
        self.lbl_num.grid(row=1, column=0, pady=(0, 10), sticky="s")

        # 事件绑定
        for w in [self, self.lbl_img, self.lbl_num]:
            w.bind("<Button-1>", self.on_click)
            w.bind("<Button-3>", self.on_right_click)
            
        self.refresh_text_ui() 

    def update_index(self, new_index):
        self.current_index = new_index
        self.refresh_text_ui()

    def refresh_text_ui(self):
        if not self.winfo_exists(): return
        is_land = self.backend.is_landscape(self.current_index)
        txt = f"{self.current_index + 1}"
        col = "gray"
        if is_land:
            txt += " (横)"
            col = "#D35400"
        self.lbl_num.configure(text=txt, text_color=col if not self.is_selected else "#1F6AA5")

    def set_image(self, pil_image):
        if not self.winfo_exists() or not pil_image: return
        try:
            ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=pil_image.size)
            self.lbl_img.configure(image=ctk_img, text="")
            self.lbl_img._image = ctk_img 
            self.refresh_text_ui()
        except: pass

    def set_selected(self, selected):
        if not self.winfo_exists(): return
        self.is_selected = selected
        if selected:
            self.configure(border_width=2, border_color="#1F6AA5", fg_color="#E1F2F8")
            self.lbl_num.configure(text_color="#1F6AA5")
        else:
            self.configure(border_width=0, fg_color="transparent")
            self.refresh_text_ui()

    def on_click(self, event):
        self.select_callback(self.current_index)
        return "break"

    def on_right_click(self, event):
        if not self.is_selected:
            self.select_callback(self.current_index)
        self.menu_callback(event, self.current_index)

# ==============================================================================
# 主程序 - 重新设计：仅继承 CTkFrame
# ==============================================================================
class EditorFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        
        self.backend = PDFBackend()
        self.selected_indices = set()
        self.card_widgets = []   
        self.clipboard_pages = []
        self.image_cache = {} 
        
        self.setup_ui()
        self.create_context_menu()

    def setup_ui(self):
        # Toolbar
        self.toolbar = ctk.CTkFrame(self, height=50)
        self.toolbar.pack(fill="x", side="top")
        
        ctk.CTkButton(self.toolbar, text="📂 打开", command=self.open_file, width=70, fg_color="transparent", border_width=1, text_color=("black", "white")).pack(side="left", padx=10, pady=8)
        ctk.CTkButton(self.toolbar, text="💾 导出", command=self.save_file, width=70, fg_color="#28a745").pack(side="left", padx=5)
        
        ctk.CTkFrame(self.toolbar, width=2, height=20, fg_color="gray").pack(side="left", padx=10)
        
        # Undo/Redo Buttons
        self.btn_undo = ctk.CTkButton(self.toolbar, text="↩ 撤销", command=self.do_undo, width=70, fg_color="#6c757d", state="disabled")
        self.btn_undo.pack(side="left", padx=2)
        self.btn_redo = ctk.CTkButton(self.toolbar, text="↪ 重做", command=self.do_redo, width=70, fg_color="#6c757d", state="disabled")
        self.btn_redo.pack(side="left", padx=2)
        
        ctk.CTkFrame(self.toolbar, width=2, height=20, fg_color="gray").pack(side="left", padx=10)
        ctk.CTkButton(self.toolbar, text="⚡ 选中横向", command=self.select_landscape_pages, fg_color="#ffc107", text_color="black").pack(side="left", padx=5)
        ctk.CTkButton(self.toolbar, text="🗑 删除", command=self.delete_selected, fg_color="#dc3545", width=60).pack(side="right", padx=10)
        ctk.CTkButton(self.toolbar, text="↻ 右转", command=lambda: self.rotate_selected(-90), width=60).pack(side="right", padx=2)
        ctk.CTkButton(self.toolbar, text="↺ 左转", command=lambda: self.rotate_selected(90), width=60).pack(side="right", padx=2)
        
        self.lbl_status = ctk.CTkLabel(self.toolbar, text="就绪", text_color="gray")
        self.lbl_status.pack(side="right", padx=20)

        # Scroll Frame
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color=("white", "gray15"))
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 绑定拖放到 scroll_frame
        self.scroll_frame.drop_target_register(DND_FILES)
        self.scroll_frame.dnd_bind('<<Drop>>', self.drop_file_handler)
        
        self.scroll_frame.bind("<Button-1>", lambda e: self.clear_selection())
        self.bind("<Control-a>", self.select_all)
        self.bind("<Control-z>", lambda e: self.do_undo())
        self.bind("<Control-y>", lambda e: self.do_redo())
        
        self.lbl_hint = ctk.CTkLabel(self.scroll_frame, text="请拖入 PDF 文件或点击'打开'按钮", font=("", 20), text_color="gray")
        self.lbl_hint.pack(pady=150)

    def create_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="✂️ 剪切选中", command=self.cut_selected)
        self.context_menu.add_command(label="📋 粘贴在此处", command=self.paste_here)

    # --- 核心逻辑 ---

    def drop_file_handler(self, event):
        path = event.data
        if path.startswith('{') and path.endswith('}'): 
            path = path[1:-1]
        if path.lower().endswith('.pdf'): 
            self.load_pdf(path)



    def open_file(self):
        initial_dir = SettingsManager().get("last_file_directory")
        path = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")], initialdir=initial_dir)
        if path: 
            SettingsManager().update_last_dir(path)
            self.load_pdf(path)

    def load_pdf(self, path):
        # 隐藏提示
        if self.lbl_hint.winfo_exists():
            self.lbl_hint.pack_forget()
            
        for w in self.scroll_frame.winfo_children(): 
            w.destroy()
        self.card_widgets = []
        self.selected_indices = set()
        
        try:
            self.backend.load(path)
            self.image_cache = {} 
            self.lbl_status.configure(text=f"已加载: {os.path.basename(path)}")
            self.refresh_grid(initial=True)
        except Exception as e:
            messagebox.showerror("错误", f"无法加载PDF: {str(e)}")
            self.lbl_hint.pack(pady=150)

    def refresh_grid(self, initial=False):
        total_pages = self.backend.get_page_count()
        current_count = len(self.card_widgets)
        if total_pages == 0: return

        if current_count < total_pages:
            for i in range(current_count, total_pages):
                card = PageCard(self.scroll_frame, i, self.backend, self.on_card_select, self.show_context_menu)
                self.card_widgets.append(card)
        elif current_count > total_pages:
            for i in range(total_pages, current_count):
                self.card_widgets[i].destroy()
            self.card_widgets = self.card_widgets[:total_pages]

        cols = 5
        to_render = []

        for i in range(total_pages):
            card = self.card_widgets[i]
            card.grid(row=i//cols, column=i%cols, padx=5, pady=5)
            
            card.update_index(i)
            if i in self.selected_indices: 
                card.set_selected(True)
            else: 
                card.set_selected(False)

            orig_idx = self.backend.get_original_index(i)
            if orig_idx in self.image_cache:
                card.set_image(self.image_cache[orig_idx])
            else:
                card.lbl_img.configure(image=None, text="加载中...")
                to_render.append((i, orig_idx))

        if to_render:
            self.lbl_status.configure(text="正在加载图片...")
            threading.Thread(target=self._async_render, args=(to_render,), daemon=True).start()
        else:
            if not initial: 
                self.lbl_status.configure(text="就绪")

    def _async_render(self, tasks):
        future_to_info = {}
        with ThreadPoolExecutor(max_workers=8) as executor:
            for c_idx, o_idx in tasks:
                f = executor.submit(self.backend.render_thumbnail, o_idx)
                future_to_info[f] = (c_idx, o_idx)
            
            for f in concurrent.futures.as_completed(future_to_info):
                c_idx, o_idx = future_to_info[f]
                try:
                    img = f.result()
                    if img:
                        self.image_cache[o_idx] = img
                        self.after(0, lambda c=c_idx, im=img: self._safe_update_card(c, im))
                except: pass
        self.after(0, lambda: self.lbl_status.configure(text="加载完成"))

    def _safe_update_card(self, index, image):
        if index < len(self.card_widgets):
            self.card_widgets[index].set_image(image)

    # --- 交互操作 ---

    def on_card_select(self, index):
        if index in self.selected_indices:
            self.selected_indices.remove(index)
            self.card_widgets[index].set_selected(False)
        else:
            self.selected_indices.add(index)
            self.card_widgets[index].set_selected(True)
        self.lbl_status.configure(text=f"选中 {len(self.selected_indices)} 页")

    def clear_selection(self):
        for idx in self.selected_indices:
            if idx < len(self.card_widgets):
                self.card_widgets[idx].set_selected(False)
        self.selected_indices.clear()
        self.lbl_status.configure(text="就绪")

    def select_all(self, event=None):
        if not self.card_widgets: return
        self.selected_indices = set(range(len(self.card_widgets)))
        for card in self.card_widgets: 
            card.set_selected(True)
        self.lbl_status.configure(text=f"全选 {len(self.selected_indices)} 页")

    def select_landscape_pages(self):
        self.clear_selection()
        count = 0
        for i, card in enumerate(self.card_widgets):
            if self.backend.is_landscape(i):
                self.selected_indices.add(i)
                card.set_selected(True)
                count += 1
        self.lbl_status.configure(text=f"自动选中 {count} 个横向页")

    def rotate_selected(self, angle):
        if not self.selected_indices: return
        
        for idx in self.selected_indices:
            self.backend.rotate_page(idx, angle)
            orig_idx = self.backend.get_original_index(idx)
            if orig_idx in self.image_cache: 
                del self.image_cache[orig_idx]

        self.lbl_status.configure(text="正在刷新旋转...")
        
        def refresh_task():
            for idx in list(self.selected_indices):
                orig_idx = self.backend.get_original_index(idx)
                new_img = self.backend.render_thumbnail(orig_idx) 
                if new_img:
                    self.image_cache[orig_idx] = new_img
                    self.after(0, lambda i=idx, im=new_img: self._safe_update_card(i, im))
            self.after(0, lambda: self.lbl_status.configure(text="旋转完成"))
            self.after(0, self.update_undo_redo_buttons)

        threading.Thread(target=refresh_task, daemon=True).start()

    def delete_selected(self):
        if not self.selected_indices: return
        if not messagebox.askyesno("确认", "确定删除选中页吗?"): return
        
        sorted_indices = sorted(list(self.selected_indices), reverse=True)
        for idx in sorted_indices: 
            self.backend.delete_page(idx)
        
        self.clear_selection()
        self.refresh_grid()
        self.update_undo_redo_buttons()

    def show_context_menu(self, event, page_index):
        self.last_right_click_index = page_index
        state = "normal" if self.clipboard_pages else "disabled"
        self.context_menu.entryconfig(1, state=state)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def cut_selected(self):
        if not self.selected_indices: return
        self.clipboard_pages = self.backend.cut_pages(self.selected_indices)
        self.clear_selection()
        self.refresh_grid()
        self.lbl_status.configure(text=f"已剪切 {len(self.clipboard_pages)} 页")

    def paste_here(self):
        if not self.clipboard_pages: return
        self.backend.paste_pages(self.last_right_click_index, self.clipboard_pages)
        self.clipboard_pages = [] 
        self.refresh_grid()
        self.lbl_status.configure(text="粘贴完成")

    # --- Undo/Redo ---
    def do_undo(self):
        if self.backend.undo():
            self.clear_selection()
            self.refresh_grid()  # Refresh card layout and indices
            self.lbl_status.configure(text="正在刷新...")
            
            # Async re-render all thumbnails
            def refresh_task():
                total = self.backend.get_page_count()
                for idx in range(total):
                    orig_idx = self.backend.get_original_index(idx)
                    new_img = self.backend.render_thumbnail(orig_idx)
                    if new_img:
                        self.image_cache[orig_idx] = new_img
                        self.after(0, lambda i=idx, im=new_img: self._safe_update_card(i, im))
                self.after(0, lambda: self.lbl_status.configure(text="撤销完成"))
            
            threading.Thread(target=refresh_task, daemon=True).start()
        self.update_undo_redo_buttons()

    def do_redo(self):
        if self.backend.redo():
            self.clear_selection()
            self.refresh_grid()  # Refresh card layout and indices
            self.lbl_status.configure(text="正在刷新...")
            
            # Async re-render all thumbnails
            def refresh_task():
                total = self.backend.get_page_count()
                for idx in range(total):
                    orig_idx = self.backend.get_original_index(idx)
                    new_img = self.backend.render_thumbnail(orig_idx)
                    if new_img:
                        self.image_cache[orig_idx] = new_img
                        self.after(0, lambda i=idx, im=new_img: self._safe_update_card(i, im))
                self.after(0, lambda: self.lbl_status.configure(text="重做完成"))
            
            threading.Thread(target=refresh_task, daemon=True).start()
        self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        self.btn_undo.configure(state="normal" if self.backend.can_undo() else "disabled")
        self.btn_redo.configure(state="normal" if self.backend.can_redo() else "disabled")

    def save_file(self):
        if not self.backend.doc:
            messagebox.showwarning("提示", "请先加载PDF文件")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if path:
            try:
                self.backend.save(path)
                messagebox.showinfo("成功", "保存成功")
            except Exception as e:
                messagebox.showerror("错误", str(e))

if __name__ == "__main__":
    # Standalone testing
    from tkinterdnd2 import TkinterDnD
    
    root = TkinterDnD.Tk()
    root.geometry(Config.APP_SIZE)
    root.title(Config.APP_NAME)
    
    app = EditorFrame(root)
    app.pack(fill="both", expand=True)
    root.mainloop()