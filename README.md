
# Gwyddion Python Bridge (Windows / Gwyddion 2.69)

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

# Quick Install (for windows I.e., using the included DLL)

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

in `precompiled/Windows` there is a file 'run_gwy_py.bat'. save this file to your desktop screen (this is your new gwyddion launcher), and edit lines 4 to be the path to the python executable that runs your script:

```bat
set "GWY_PYTHON_EXE=C:\your\path\to\python.exe"
```
```bat
set "GWY_PYTHON_SCRIPT=C:\your\path\to\your\python-script\example-script.py" 
```

You are now done. Double click the bat script just like you would with the gwyddion desktop short cut and your python script will be a module inside **Data Process → STM → Run Python Script**


# Not windows

I have not compiled for unix based platforms. Hence you will need to compile it yourself, and amend the bat script (to bash) to launch gwyddion with the correct environment variables for your platform. 
## 1) Build From Source (MSYS2 MinGW64, Win64)

You only need this if:

* the DLL doesn’t load on another machine (dependency mismatch), or
* you want to modify the C module.

If it helps compilation for unix based systems, this is what i did to compile for windows.

> Note: for more details beyond this the README for the template module as written by Gwyddion is included in src. I only rewrote the c-code from the module (and kept the temporary name they used) found in src/threshold-example.c
---

## 0) Install MSYS2

Install MSYS2, then open **“MSYS2 MinGW x64”** (not the plain MSYS shell).

---

## 1) Update + install toolchain

In MSYS2 MinGW x64:

```bash
pacman -Syu
# close/reopen when prompted
pacman -Syu

pacman -S --needed \
  mingw-w64-x86_64-toolchain \
  mingw-w64-x86_64-pkgconf \
  autoconf automake libtool make git curl tar
```

---

## 2) Install Gwyddion build dependencies (MSYS2 packages)

```bash
pacman -S --needed \
  mingw-w64-x86_64-gtk2 \
  mingw-w64-x86_64-glib2 \
  mingw-w64-x86_64-libxml2 \
  mingw-w64-x86_64-zlib \
  mingw-w64-x86_64-libpng \
  mingw-w64-x86_64-libtiff \
  mingw-w64-x86_64-libjpeg-turbo \
  mingw-w64-x86_64-fftw \
  mingw-w64-x86_64-gsl \
  mingw-w64-x86_64-hdf5 \
  mingw-w64-x86_64-gtkglext
```

If `./configure` says something is missing later, install the named
`mingw-w64-x86_64-...` package and rerun.

---

## 3) Build & install Gwyddion 2.69 **into MSYS2** (gives you `gwyddion.pc`)

module builds use `pkg-config` and **require** a working `gwyddion.pc`.

```bash
mkdir -p /c/gwyddion-dev
cd /c/gwyddion-dev

curl -L -o gwyddion-2.69.tar.xz \
  "https://sourceforge.net/projects/gwyddion/files/gwyddion/2.69/gwyddion-2.69.tar.xz/download"

tar -xf gwyddion-2.69.tar.xz
cd gwyddion-2.69

./configure --prefix=/mingw64
make -j$(nproc)
make install
```

Verify:

```bash
pkg-config --modversion gwyddion
pkg-config --cflags --libs gwyddion
```

**Do not continue** until `pkg-config gwyddion` works.

---

## 4) Build the module

Assuming your module sources are at:

```
C:\gwy-python-bridge\module\
```

In MSYS2 MinGW x64:

```bash
cd /c/gwy-python-bridge/module
make clean || true

# Install to the Windows user modules folder
./configure --with-dest="$(cygpath -u "$USERPROFILE")/gwyddion/modules/process"

make
make install
```

The built DLL is usually also available under:

```
./.libs/
```

---

## 5) Load it in Gwyddion

1. Close all instances of Gwyddion (best way to do this is to check Task Manager for `gwyddion.exe`)
2. Start via your BAT launcher
3. Verify menu:

   * Data Process → STM → Run Python Script

---

# License

This project contains code derived from/compatible with Gwyddion module templates and uses Gwyddion APIs.

