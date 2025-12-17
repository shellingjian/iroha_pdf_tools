import customtkinter as ctk
from tkinterdnd2 import TkinterDnD
import multiprocessing
import os
import sys
from config import GlobalConfig
from settings_manager import SettingsManager

# Import the refactored frames
# Ensure current directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from iRoha_PDF_Editor import EditorFrame
from iRoha_PDF_Merger import MergerFrame
from iRoha_PDF_Paginator import PaginatorFrame
from iRoha_PDF_Img2Pdf import Img2PdfFrame

from PIL import Image

# Initialize Settings
settings = SettingsManager()
settings.apply_startup_settings()
ctk.set_default_color_theme(GlobalConfig.THEME_COLOR)

class MainApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        # Initialize DnD
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title(f"{GlobalConfig.APP_NAME} v{GlobalConfig.APP_VERSION}")
        self.geometry(GlobalConfig.APP_SIZE)

        # Set icon
        try:
            icon_path = self.get_asset_path("icons/icon_main.ico")
            self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Icon load error: {e}")
        
        # Layout: Sidebar + Content
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.load_icons()
        self.create_ui()
        
        # Load last used mode into menu
        self.mode_menu.set(settings.get("appearance_mode"))

    def load_icons(self):
        self.icons = {}
        try:
            self.icons["editor"] = ctk.CTkImage(light_image=Image.open(self.get_asset_path("icons/icon_editor.ico")), size=(20, 20))
            self.icons["merger"] = ctk.CTkImage(light_image=Image.open(self.get_asset_path("icons/icon_merger.ico")), size=(20, 20))
            self.icons["paginator"] = ctk.CTkImage(light_image=Image.open(self.get_asset_path("icons/icon_paginator.ico")), size=(20, 20))
            self.icons["img2pdf"] = ctk.CTkImage(light_image=Image.open(self.get_asset_path("icons/icon_img2pdf.ico")), size=(20, 20))
        except Exception as e:
            print(f"Error loading icons: {e}")

    def get_asset_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, "assets", relative_path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", relative_path)

    def create_ui(self):
        # --- Navigation Sidebar ---
        self.nav_frame = ctk.CTkFrame(self, corner_radius=0)
        self.nav_frame.grid(row=0, column=0, sticky="nsew")
        self.nav_frame.grid_rowconfigure(6, weight=1)

        # Logo
        try:
            logo_img = ctk.CTkImage(light_image=Image.open(self.get_asset_path("icons/logo.png")), size=(100, 100))
            self.logo = ctk.CTkLabel(self.nav_frame, text="", image=logo_img)
            self.logo.grid(row=0, column=0, padx=20, pady=(30, 20))
        except:
             self.logo = ctk.CTkLabel(self.nav_frame, text="iRoha PDF\nToolkit", font=ctk.CTkFont(size=24, weight="bold"))
             self.logo.grid(row=0, column=0, padx=20, pady=(30, 30))

        # Nav Buttons
        self.nav_buttons = []
        self.create_nav_button("PDF编辑", "editor", self.icons.get("editor"), 1)
        self.create_nav_button("PDF合并", "merger", self.icons.get("merger"), 2)
        self.create_nav_button("PDF页码", "paginator", self.icons.get("paginator"), 3)
        self.create_nav_button("图片转PDF", "img2pdf", self.icons.get("img2pdf"), 4)
        
        # Appearance Mode
        self.lbl_mode = ctk.CTkLabel(self.nav_frame, text="主题:", anchor="w")
        self.lbl_mode.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")
        self.mode_menu = ctk.CTkOptionMenu(self.nav_frame, values=["System", "Light", "Dark"],
                                           command=self.change_appearance_mode)
        self.mode_menu.grid(row=8, column=0, padx=20, pady=(0, 20), sticky="s")

        # --- Content Area ---
        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        
        self.frames = {}
        self.active_btn_name = None
        
        # Show default frame
        self.show_frame("editor")

    def create_nav_button(self, text, name, icon, row):
        btn = ctk.CTkButton(self.nav_frame, 
                            text=text,
                            image=icon,
                            compound="left",
                            height=40,
                            fg_color="transparent", 
                            text_color=("gray10", "gray90"),
                            hover_color=("gray70", "gray30"),
                            anchor="w",
                            font=ctk.CTkFont(size=15),
                            command=lambda n=name: self.show_frame(n))
        btn.grid(row=row, column=0, sticky="ew", padx=10, pady=5)
        self.nav_buttons.append((name, btn))

    def show_frame(self, name):
        # Update Buttons
        for n, btn in self.nav_buttons:
            if n == name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")
        
        # Hide all frames
        for frame in self.frames.values():
            frame.pack_forget()
            
        # Lazy load frame
        if name not in self.frames:
            if name == "editor":
                self.frames[name] = EditorFrame(self.content_frame)
            elif name == "merger":
                self.frames[name] = MergerFrame(self.content_frame)
            elif name == "paginator":
                self.frames[name] = PaginatorFrame(self.content_frame)
            elif name == "img2pdf":
                self.frames[name] = Img2PdfFrame(self.content_frame)
        
        # Show selected
        self.frames[name].pack(fill="both", expand=True)

    def change_appearance_mode(self, new_appearance_mode):
        ctk.set_appearance_mode(new_appearance_mode)
        SettingsManager().set("appearance_mode", new_appearance_mode)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from tkinterdnd2 import TkinterDnD
    root = MainApp()
    root.mainloop()

