import PyInstaller.__main__
import os
import tkinterdnd2
import customtkinter

def build():
    # Define paths
    # We are running from src/build.py, but we should run it from project root context usually
    # Let's assume this script is run from project root, or we handle paths absolutely
    
    project_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    src_dir = os.path.join(project_dir, 'src')
    main_script = os.path.join(src_dir, 'main_app.py')
    icon_path = os.path.join(src_dir, 'assets', 'icon_main.ico')
    
    # Assets folder: src/assets -> assets in dist
    assets_path = os.path.join(src_dir, 'assets')
    
    # Lib paths
    tkdnd_path = os.path.dirname(tkinterdnd2.__file__)
    ctk_path = os.path.dirname(customtkinter.__file__)
    
    print(f"Building from: {main_script}")
    print(f"Icon: {icon_path}")
    print(f"TkinterDnD: {tkdnd_path}")
    print(f"CustomTkinter: {ctk_path}")

    args = [
        main_script,
        '--name=iRohaPDFToolkit',
        '--onefile',
        '--noconsole',
        '--clean',
        f'--icon={icon_path}',
        # Add Data: SourcePath;DestPath (Windows uses ;)
        f'--add-data={tkdnd_path};tkinterdnd2',
        f'--add-data={ctk_path};customtkinter',
        f'--add-data={assets_path};assets',
        
        # Hidden imports
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=tkinterdnd2',
        '--hidden-import=customtkinter',
        '--hidden-import=pymupdf',
        '--hidden-import=fitz',

        # Excludes (Optimization)
        '--exclude-module=matplotlib',
        '--exclude-module=pandas',
        '--exclude-module=scipy',
        '--exclude-module=rembg',
        '--exclude-module=onnxruntime',
        '--exclude-module=notebook',
        '--exclude-module=ipython',
        '--exclude-module=tornado',
        '--exclude-module=bokeh',
        '--exclude-module=colorama',  # used by rembg, not app
        '--exclude-module=tqdm',      # used by rembg, not app
        
        # Output directory
        f'--distpath={os.path.join(project_dir, "dist")}',
        f'--workpath={os.path.join(project_dir, "build")}',
        f'--specpath={project_dir}',
    ]
    
    PyInstaller.__main__.run(args)

if __name__ == "__main__":
    build()
