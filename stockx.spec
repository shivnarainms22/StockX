# PyInstaller spec — StockX (one-folder, windowed, portable).
# Build:  python build.py   (or: pyinstaller stockx.spec --noconfirm)
#
# The ML/embedding stack is EXCLUDED. chromadb pulls sentence-transformers ->
# torch (gigabytes), which makes the build crawl for many minutes and balloons
# the bundle. None of it is needed at runtime: memory/store.py falls back to its
# JSONL backend when chromadb is unavailable. scipy/matplotlib/numpy/yfinance use
# PyInstaller's reliable built-in hooks, so no collect_all is needed.
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = []
hiddenimports += collect_submodules("PyQt6")
hiddenimports += collect_submodules("plyer")  # dynamic per-platform notification backends

_EXCLUDES = [
    "chromadb", "onnxruntime",
    "torch", "torchvision", "torchaudio",
    "transformers", "sentence_transformers", "tokenizers",
    "sympy", "tkinter",
]

a = Analysis(
    ["run_gui.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=_EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StockX",
    console=False,
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="StockX",
)
