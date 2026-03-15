
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