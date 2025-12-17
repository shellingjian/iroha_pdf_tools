# iRoha PDF Toolkit

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

一个轻量级、功能强大的本地化 PDF 工具箱。无需上传文件到云端，保护您的隐私。

## ✨ 主要功能

本工具箱集成了以下四大核心模块：

1.  **📄 PDF 编辑器 (Editor)**
    *   **可视化页面管理**: 拖拽排序、删除页面。
    *   **页面旋转**: 支持单页或批量旋转。
    *   **提取页面**: 另存选定页面为新 PDF。

2.  **🔗 PDF 合并 (Merger)**
    *   **批量合并**: 将多个 PDF 文件合并为一个。
    *   **智能排序**: 支持手动拖拽排序。

3.  **🔢 PDF 页码 (Paginator)**
    *   **智能加页码**: 支持多种页码格式 (如 "第 x 页 / 共 y 页")。
    *   **样式自定义**: 可调整字体大小、颜色、位置。
    *   **扫描件修复**: 即使是扫描版 PDF 也能准确添加页码。

4.  **🖼️ 图片转 PDF (Img2Pdf)**
    *   **批量转换**: 将 JPG, PNG, HEIC 等图片转换为 PDF。
    *   **拼图模式**: 支持多张图片合并到一页 A4 纸 (类似证件复印)。
    *   **智能压缩**: 自动压缩图片以减小文件体积。

## 🚀 安装与运行

### 方式一：直接运行 (推荐开发者)

1.  克隆仓库:
    ```bash
    git clone https://github.com/your-username/iroha_pdf_tools.git
    cd iroha_pdf_tools
    ```

2.  创建虚拟环境并安装依赖:
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    
    pip install -r requirements.txt
    ```

3.  运行主程序:
    ```bash
    python src/main_app.py
    ```

### 方式二：下载 EXE

请前往 [Releases](https://github.com/your-username/iroha_pdf_tools/releases) 页面下载最新的 `iRohaPDFToolkit.exe`，无需安装 Python 环境即可使用。

## 🛠️ 技术栈

*   **GUI**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (现代化 UI)
*   **PDF Core**: [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) (高性能 PDF 处理)
*   **Drag & Drop**: [TkinterDnD2](https://github.com/pmgagne/tkinterdnd2)
*   **Build**: PyInstaller

## 📝 开发与维护

项目结构如下：
```
src/
├── iRoha_PDF_Editor.py   # 编辑器模块
├── iRoha_PDF_Merger.py   # 合并模块
├── iRoha_PDF_Paginator.py# 页码模块
├── iRoha_PDF_Img2Pdf.py  # 图片转PDF模块
├── main_app.py           # 主程序入口
├── config.py             # 配置中心
├── utils.py              # 通用工具函数
└── settings_manager.py   # 用户配置管理
```

打包发布:
```bash
pyinstaller --clean iRohaPDFToolkit.spec
```

## 📄 许可证

本项目采用 MIT 许可证。
