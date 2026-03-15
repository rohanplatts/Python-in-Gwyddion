import sys
import numpy as np

def absurd_process(img):
    p1, p99 = np.percentile(img, [1, 99])
    img = np.clip(img, p1, p99)

    ny, nx = img.shape
    mid = nx // 2

    left = img[:, :mid]
    right = img[:, mid:]

    left_flat = left - left.mean()
    right_new = np.full_like(right, left_flat.mean())

    out = np.zeros_like(img, dtype=np.float64)
    out[:, :mid] = left_flat
    out[:, mid:] = right_new
    return out

def main():
    inpath, outpath = sys.argv[1], sys.argv[2]
    img = np.load(inpath)          # float64, shape (ny,nx)
    out = absurd_process(img)
    np.save(outpath, out.astype(np.float64))

if __name__ == "__main__":
    main()
