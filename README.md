
# Gwyddion Python Bridge (Windows 64 bit / Gwyddion 2.69)

This project provides a **Gwyddion process module** that readds python to Gwyddion via 
a c module. For a windows user, all they need to do is copy the supplied .dll file into 
the gwyddion modules folder, and then supply the path to the python executable and python script and they shall be ready to execute that code in gwyddion on its next launch. 

**Data Process → STM → Run Python Script**

When clicked, it:
1) exports the **current channel** to a temporary `in.npy`  
2) runs your Python: `python script.py in.npy out.npy`  
3) loads `out.npy` and overwrites the current channel

**Windows Win64 only** in this repo release (contains a `.dll`).  
No Linux/macOS binaries are included.

Tested on windows with Gwyddion 2.69 

---

# Python Script 

Your script must accept:

```
python process.py <in.npy> <out.npy>
```

* input: `float64` NumPy array, shape `(ny, nx)`
* output: must write `float64` array with the **same shape**

Minimal template:

```python
import sys
import numpy as np
import yaml
import os

def process(img: np.ndarray, cfg: dict) -> np.ndarray:
    # TODO: your logic here
    # REMEMBER: It can depend on a config file! so if you would like to iteratively 
    # tweek a process on a particular file, that is possible by modifying and saving 
    # the config file (or of course, by directly modifying the python script)
    return img.astype(np.float64)

def main():
    inpath, outpath = sys.argv[1], sys.argv[2]
    img = np.load(inpath)
    # here we suppose that you add a config.yml somewhere, and then 
    # add the config.yml path to the .bat environment variables (explained below)
    cfg_path = os.environ.get("GWY_PYTHON_CONFIG", "")
    cfg = {}
    if cfg_path:
        with open(cfg_path, "r") as f:
            cfg = yaml.safe_load(f) or {}

    out = process(img, cfg)
    np.save(outpath, out.astype(np.float64))

if __name__ == "__main__":
    main()
```

## How it works
The module does **not** compile your Python into the DLL.  
Each click spawns Python using **environment variables** set when Gwyddion starts:

- `GWY_PYTHON_EXE` = full path to `python.exe` (e.g. your conda env python)
- `GWY_PYTHON_SCRIPT` = full path to your `.py` script
- (optional) `GWY_PYTHON_CONFIG` = full path to a config file your script loads

This means:
- Editing the `.py` file **does not require recompiling** the DLL.
- Editing a `config.yml` the script reads **changes behaviour immediately** on next click (even while Gwyddion stays open).
- Changing `GWY_PYTHON_EXE` / `GWY_PYTHON_SCRIPT` usually requires **restarting Gwyddion** (env vars are captured at process start).

---

# Quick Install (for windows 64 I.e., using the included DLL)

## 1) Install the module DLL (user modules directory)
Copy the DLL (located in `precompiled/windows/threshold-example.dll`) into:

**Windows user modules folder**
```

C:\Users<YOU>\gwyddion\modules\process\

```

Example:
```

C:\Users\rnpla\gwyddion\modules\process\threshold-example.dll

```

> Note: Some builds may also use `C:\Users\<YOU>\.gwyddion\...`, but on Windows the folder that actually worked here is `C:\Users\<YOU>\gwyddion\...`.

## 2) Use the launcher BAT

in `precompiled/Windows` there is a file 'run_gwy_py.bat'. save this file to your desktop screen (this is your new gwyddion launcher), and edit lines 4 and 5to be the path to the python executable that runs your script, and the path to the python script respectively:

```bat
set "GWY_PYTHON_EXE=C:\your\path\to\python.exe"
```
```bat
set "GWY_PYTHON_SCRIPT=C:\your\path\to\your\python-script\example-script.py" 
```

You are now done. Double click the bat script just like you would with the gwyddion desktop short cut and your python script will be a module inside **Data Process → STM → Run Python Script**


---
# Examples

This repo includes two demo scripts you can run via the Gwyddion Python bridge.

### 1) `absurd_process.py` (default)
- A simple “obvious” test: it clips the image to the 1–99 percentile, then **wipes the right half** by filling it with a constant derived from the left half.
- The provided `precompiled/windows/run_gwy_py.bat` already points to `tool_python_scripts\absurd_process.py`.
- its an absurd script haha, only meant to show you that it works, however you can begin to see how it manipulates the data.

### 2) `quicksegment.py` (advanced demo)
- Applies a segmentation pipeline with:
  - global plane fit + flattening
  - TV denoise + Gaussian smoothing + Sobel edge map
  - **interactive marker selection** (TkAgg popup) to seed watershed
- To run it, set `GWY_PYTHON_SCRIPT` in your launcher BAT to `path\to\quicksegment.py` (after downloading the script and the pyproject.toml) and install the necessary dependencies by runnning `pip install -e .` in the directory containing the pyproject.toml file. Ensure your Python env has `tkinter` available for the GUI. Then, as before, once you set the python executable path in your .bat launcher, you'll be ready to go. 

# License

This project contains code derived from/compatible with Gwyddion module templates and uses Gwyddion APIs.

