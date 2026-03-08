# =============================================================================
# camera_path.py — 攝影機路徑插值器
#
# 職責：讀取 config.CAMERA_KEYFRAMES，產生每一幀的
#        (azimuth, elevation, distance) 三元組陣列。
#
# 緩動函數比喻：
#   linear          → 機器人走路，勻速、生硬
#   ease_in_out     → 電車啟動與進站，自然加減速
#   critically_damped → 彈簧門，帶一點慣性感，不會過衝
# =============================================================================

from __future__ import annotations
import numpy as np
import config as cfg


# ---------------------------------------------------------------------------
# 緩動函數（都定義在 t ∈ [0, 1] → [0, 1]）
# ---------------------------------------------------------------------------

def _ease_in_out(t: np.ndarray) -> np.ndarray:
    """平滑 S 曲線（smoothstep），慢進慢出。"""
    return t * t * (3.0 - 2.0 * t)


def _critically_damped(t: np.ndarray) -> np.ndarray:
    """
    臨界阻尼彈簧響應（解析解，omega 從 config 讀取）。

    物理原理：臨界阻尼是「最快收斂且不震盪」的阻尼比（zeta=1）。
    解析解：x(t) = 1 - e^{-omega*t} * (1 + omega*t)

    比喻：像一扇裝了液壓緩衝器的高級車門——
          推開時一開始需要施力（慢起步），
          中段順暢加速，
          快到位時液壓自動抵抗，緩緩停下，完全不反彈。

    與 ease_in_out 的差異：
      ease_in_out 是對稱 S 曲線（起步=收尾）
      critically_damped 是非對稱的——起步更慢，收尾拖曳感更強，
      更接近真實攝影機的物理慣性。
    """
    omega = cfg.CAMERA_DAMPING_OMEGA
    val  = 1.0 - np.exp(-omega * t) * (1.0 + omega * t)
    norm = 1.0 - np.exp(-omega)     * (1.0 + omega)      # t=1 時的值，用於正規化
    return np.clip(val / (norm + 1e-8), 0, 1)


def _linear(t: np.ndarray) -> np.ndarray:
    return t


_EASING_FUNCS = {
    "ease_in_out":       _ease_in_out,
    "critically_damped": _critically_damped,
    "linear":            _linear,
}


# ---------------------------------------------------------------------------
# 主介面
# ---------------------------------------------------------------------------

def build_camera_path() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    依據 config.CAMERA_KEYFRAMES 與 config.CAMERA_EASING，
    產生每一幀對應的攝影機參數。

    Returns
    -------
    azimuths   : (N,) float64，每幀方位角（度）
    elevations : (N,) float64，每幀仰角（度）
    distances  : (N,) float64，每幀距離
    N = VIDEO_FPS × VIDEO_DURATION_SEC
    """
    kfs       = cfg.CAMERA_KEYFRAMES
    total     = cfg.VIDEO_FPS * cfg.VIDEO_DURATION_SEC
    duration  = cfg.VIDEO_DURATION_SEC
    easing_fn = _EASING_FUNCS.get(cfg.CAMERA_EASING, _ease_in_out)

    # 驗證關鍵影格
    if len(kfs) < 2:
        raise ValueError("[camera_path] CAMERA_KEYFRAMES 至少需要 2 個關鍵影格。")
    if kfs[0]["t"] != 0.0:
        raise ValueError("[camera_path] 第一個關鍵影格的 t 必須為 0.0。")
    if abs(kfs[-1]["t"] - duration) > 1e-6:
        raise ValueError(
            f"[camera_path] 最後一個關鍵影格的 t={kfs[-1]['t']} "
            f"必須等於 VIDEO_DURATION_SEC={duration}。"
        )

    # 每幀的絕對時間
    frame_times = np.linspace(0.0, duration, total, endpoint=False)

    azimuths   = np.zeros(total)
    elevations = np.zeros(total)
    distances  = np.zeros(total)

    # 對每個關鍵影格區間做插值
    for i in range(len(kfs) - 1):
        t0, t1 = kfs[i]["t"], kfs[i+1]["t"]
        seg_mask = (frame_times >= t0) & (frame_times < t1)

        if not np.any(seg_mask):
            continue

        # 把區間時間正規化到 [0, 1]
        t_norm = (frame_times[seg_mask] - t0) / (t1 - t0)
        alpha  = easing_fn(t_norm)    # 套用緩動

        for key, arr in [("azimuth",   azimuths),
                          ("elevation", elevations),
                          ("distance",  distances)]:
            v0 = kfs[i][key]
            v1 = kfs[i+1][key]
            arr[seg_mask] = v0 + alpha * (v1 - v0)

    # 最後一幀補齊（endpoint=False 不含終點）
    azimuths[-1]   = kfs[-1]["azimuth"]
    elevations[-1] = kfs[-1]["elevation"]
    distances[-1]  = kfs[-1]["distance"]

    return azimuths, elevations, distances


def preview_path() -> None:
    """
    印出每幀數值預覽，不渲染影像，用來快速確認路徑是否合理。
    用法：python camera_path.py
    """
    az, el, dist = build_camera_path()
    total = len(az)
    fps   = cfg.VIDEO_FPS
    print(f"{'幀':>5}  {'時間(s)':>7}  {'方位角':>8}  {'仰角':>8}  {'距離':>8}")
    print("-" * 48)
    # 每秒印一行
    for i in range(0, total, fps):
        t = i / fps
        print(f"{i:>5}  {t:>7.2f}  {az[i]:>8.2f}°  {el[i]:>8.2f}°  {dist[i]:>8.2f}")
    # 最後一幀
    print(f"{total-1:>5}  {(total-1)/fps:>7.2f}  "
          f"{az[-1]:>8.2f}°  {el[-1]:>8.2f}°  {dist[-1]:>8.2f}")


if __name__ == "__main__":
    preview_path()