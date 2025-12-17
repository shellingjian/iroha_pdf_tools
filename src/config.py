# ==============================================================================
# 全局配置中心
# ==============================================================================

class GlobalConfig:
    APP_VERSION = "0.1.0"
    APP_NAME = "iRoha PDF Toolkit"
    APP_SIZE = "1100x800"
    THEME_COLOR = "blue"
    APPEARANCE_MODE = "System"
    
class EditorConfig:
    APP_NAME = f"PDF编辑 v{GlobalConfig.APP_VERSION}"
    APP_SIZE = "1280x850"
    
    # 定义固定的卡片尺寸
    CARD_WIDTH = 200   
    CARD_HEIGHT = 240  
    
    # 图片的最大限制尺寸
    IMG_MAX_SIZE = 160 

class MergerConfig:
    APP_NAME = f"PDF合并 v{GlobalConfig.APP_VERSION}"
    APP_SIZE = "900x700"

class PaginatorConfig:
    APP_NAME = f"PDF页码 v{GlobalConfig.APP_VERSION}"
    APP_SIZE = "1100x850"

class Img2PdfConfig:
    APP_NAME = f"图片转PDF v{GlobalConfig.APP_VERSION}"
    APP_SIZE = "1000x850"
    
    A4_W = 595
    A4_H = 842
    MARGIN = 20
    GAP = 10
    TEXT_H = 20
    
    INITIAL_LOAD_COUNT = 30 

 
