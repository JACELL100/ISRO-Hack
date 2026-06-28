"""
Scipy compatibility shim.
If scipy is installed, use it. Otherwise fall back to pure-numpy implementations
so the backend can start and serve the frontend while scipy is still downloading.
"""
import numpy as np

try:
    from scipy.ndimage import (
        gaussian_filter as _gaussian_filter,
        uniform_filter as _uniform_filter,
        label as _label,
        binary_dilation as _binary_dilation,
        binary_erosion as _binary_erosion,
        minimum_filter as _minimum_filter,
        maximum_filter as _maximum_filter,
        distance_transform_edt as _distance_transform_edt,
        gaussian_filter1d as _gaussian_filter1d,
    )
    SCIPY_AVAILABLE = True
    print("✅ scipy available — full scientific mode")
except ImportError:
    SCIPY_AVAILABLE = False
    print("⚠️  scipy not installed — using numpy fallbacks (reduced accuracy)")

    # ── Pure-numpy fallbacks ──────────────────────────────────────────────────

    def _gaussian_filter(arr: np.ndarray, sigma=1, **kwargs) -> np.ndarray:
        """Simple box-filter approximation of Gaussian blur."""
        from numpy.lib.stride_tricks import sliding_window_view
        arr = np.asarray(arr, dtype=float)
        k = max(1, int(sigma * 3) | 1)  # Odd kernel size
        pad = k // 2
        padded = np.pad(arr, pad, mode='edge')
        kernel = np.ones((k, k)) / (k * k)
        result = np.zeros_like(arr, dtype=float)
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                result[i, j] = padded[i:i+k, j:j+k].mean()
        return result

    def _uniform_filter(arr: np.ndarray, size=3, **kwargs) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        k = size if isinstance(size, int) else size[0]
        pad = k // 2
        padded = np.pad(arr, pad, mode='edge')
        result = np.zeros_like(arr, dtype=float)
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                result[i, j] = padded[i:i+k, j:j+k].mean()
        return result

    def _label(arr: np.ndarray, **kwargs):
        """Connected component labeling (4-connectivity, simple flood fill)."""
        arr = (arr > 0).astype(int)
        labeled = np.zeros_like(arr)
        current_label = 0
        for r in range(arr.shape[0]):
            for c in range(arr.shape[1]):
                if arr[r, c] and not labeled[r, c]:
                    current_label += 1
                    # BFS
                    queue = [(r, c)]
                    while queue:
                        cr, cc = queue.pop()
                        if 0 <= cr < arr.shape[0] and 0 <= cc < arr.shape[1]:
                            if arr[cr, cc] and not labeled[cr, cc]:
                                labeled[cr, cc] = current_label
                                queue.extend([(cr+1,cc),(cr-1,cc),(cr,cc+1),(cr,cc-1)])
        return labeled, current_label

    def _binary_dilation(arr: np.ndarray, iterations=1, **kwargs) -> np.ndarray:
        arr = arr.astype(bool)
        for _ in range(iterations):
            result = arr.copy()
            result[1:] |= arr[:-1]
            result[:-1] |= arr[1:]
            result[:, 1:] |= arr[:, :-1]
            result[:, :-1] |= arr[:, 1:]
            arr = result
        return arr

    def _binary_erosion(arr: np.ndarray, iterations=1, **kwargs) -> np.ndarray:
        arr = arr.astype(bool)
        for _ in range(iterations):
            result = arr.copy()
            result[1:] &= arr[:-1]
            result[:-1] &= arr[1:]
            result[:, 1:] &= arr[:, :-1]
            result[:, :-1] &= arr[:, 1:]
            arr = result
        return arr

    def _minimum_filter(arr: np.ndarray, size=3, **kwargs) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        k = size if isinstance(size, int) else size[0]
        pad = k // 2
        padded = np.pad(arr, pad, mode='edge')
        result = np.zeros_like(arr)
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                result[i, j] = padded[i:i+k, j:j+k].min()
        return result

    def _maximum_filter(arr: np.ndarray, size=3, **kwargs) -> np.ndarray:
        arr = np.asarray(arr, dtype=float)
        k = size if isinstance(size, int) else size[0]
        pad = k // 2
        padded = np.pad(arr, pad, mode='edge')
        result = np.zeros_like(arr)
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                result[i, j] = padded[i:i+k, j:j+k].max()
        return result

    def _distance_transform_edt(arr: np.ndarray, **kwargs) -> np.ndarray:
        """Approximate EDT using iterative dilation counting."""
        arr = (arr == 0).astype(float)
        dist = np.zeros_like(arr)
        remaining = arr.copy()
        d = 0
        while remaining.any():
            d += 1
            dilated = _binary_dilation(remaining.astype(bool))
            new_pixels = dilated & (~remaining.astype(bool))
            dist[new_pixels] = d
            remaining = remaining + new_pixels.astype(float)
            if d > min(arr.shape):
                break
        return dist

    def _gaussian_filter1d(arr: np.ndarray, sigma=1, **kwargs) -> np.ndarray:
        k = max(1, int(sigma * 3) | 1)
        kernel = np.exp(-0.5 * (np.arange(k) - k//2)**2 / sigma**2)
        kernel /= kernel.sum()
        return np.convolve(arr, kernel, mode='same')


# Public API — always use these regardless of scipy availability
gaussian_filter = _gaussian_filter
uniform_filter = _uniform_filter
label = _label
binary_dilation = _binary_dilation
binary_erosion = _binary_erosion
minimum_filter = _minimum_filter
maximum_filter = _maximum_filter
distance_transform_edt = _distance_transform_edt
gaussian_filter1d = _gaussian_filter1d

try:
    from scipy.optimize import brentq
except ImportError:
    def brentq(f, a, b, **kwargs):
        """Simple bisection fallback for brentq."""
        for _ in range(100):
            mid = (a + b) / 2
            if abs(b - a) < 1e-8:
                break
            if f(a) * f(mid) < 0:
                b = mid
            else:
                a = mid
        return (a + b) / 2
