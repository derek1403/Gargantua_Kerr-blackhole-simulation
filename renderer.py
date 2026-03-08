# =============================================================================
# renderer.py — 主渲染引擎
#
# 職責：
#   1. 呼叫 physics.rk4_step 推進光子
#   2. 偵測光子穿越吸積盤（z 軸過零點）
#   3. 計算吸積盤密度、都卜勒效應、Alpha 合成
#   4. 把逃逸光線映射到背景星空
#   5. 回傳 (resolution, resolution, 3) float32 RGB 陣列 [0,1]
#
# 所有物理與幾何細節由 physics.py / camera.py 提供。
# 所有可調參數從 config.py 讀取。
# =============================================================================

from __future__ import annotations
import numpy as np
import os

import config as cfg
from physics import rk4_step, compute_impact_parameter
from camera  import build_camera, generate_rays


# ---------------------------------------------------------------------------
# 內部工具：簡易黑體色彩映射（仿 matplotlib afmhot）
# ---------------------------------------------------------------------------
def _hot_colormap(intensity: np.ndarray) -> np.ndarray:
    """
    intensity : (N,) float [0, 1]
    returns   : (N, 3) float RGB [0, 1]
    黑 → 紅 → 橙 → 黃 → 白
    """
    r = np.clip(intensity * 2.0,       0, 1)
    g = np.clip(intensity * 2.0 - 1.0, 0, 1)
    b = np.clip(intensity * 4.0 - 3.0, 0, 1)
    return np.column_stack((r, g, b))


# ---------------------------------------------------------------------------
# 內部工具：吸積盤密度場
# ---------------------------------------------------------------------------
def _disk_density(R: np.ndarray) -> np.ndarray:
    """
    給定打到吸積盤平面上的半徑 R，回傳物質密度。

    設計邏輯：
      - base_density  : 冪律衰減，內緣最濃
      - gaps          : 高斯函數「挖」出間隙（土星環效果）
      - small_gaps    : 更細的微縫
      - ripples       : sin 紋理
      - edge_falloff  : 邊緣平滑衰減，避免硬切邊
    """
    r_in  = cfg.R_IN
    r_out = cfg.R_OUT

    base = 4.0 * (r_in / np.maximum(R, r_in)) ** 3.5

    # --- 主要間隙 ---
    if cfg.ENABLE_DISK_GAPS:
        g1 = 1.0 - 0.95 * np.exp(-((R -  7.5)**2) / 0.15)
        g2 = 1.0 - 0.80 * np.exp(-((R -  9.5)**2) / 0.10)
        g3 = 1.0 - 0.60 * np.exp(-((R - 12.0)**2) / 0.08)
        g4 = 1.0 - 0.50 * np.exp(-((R - 14.0)**2) / 0.06)
        base *= g1 * g2 * g3 * g4

    # --- 微小縫隙 ---
    if cfg.ENABLE_SMALL_GAPS:
        sg1 = 1.0 - 0.40 * np.exp(-((R -  5.0)**2) / 0.80)
        sg2 = 1.0 - 0.30 * np.exp(-((R - 10.0)**2) / 0.45)
        sg3 = 1.0 - 0.20 * np.exp(-((R - 11.0)**2) / 0.38)
        base *= sg1 * sg2 * sg3

    # --- 邊緣衰減 ---
    if cfg.ENABLE_EDGE_FALLOFF:
        outer = np.clip((r_out + 1.0 - R) / 1.5,       0, 1)
        inner = np.clip((R - (r_in - 0.5)) / 0.5,      0, 1)
        base *= outer * inner

    # --- sin 波紋 ---
    singap = 0.8 * np.abs(np.sin(R * 3.0 * R.shape[0] / 100.0))
    if cfg.ENABLE_RIPPLES:
        ripples = 0.9 + 0.1 * np.sin(R * 15.0)
        base *= ripples
        alpha_blend = 0.1
        base = (1 - alpha_blend) * base + alpha_blend * singap

    return base


# ---------------------------------------------------------------------------
# 內部工具：載入背景星空
# ---------------------------------------------------------------------------
def _load_background(path: str):
    """
    回傳 (sky_img: np.ndarray float32, use_bg: bool)
    sky_img shape: (H, W, 3), values in [0, 1]
    """
    if not cfg.ENABLE_BACKGROUND_IMAGE or not os.path.exists(path):
        if cfg.ENABLE_BACKGROUND_IMAGE:
            print(f"[renderer] 找不到背景圖 {path}，改用純黑背景。")
        return None, False

    try:
        import cv2
        raw = cv2.imread(path).astype(np.float32) / 255.0
        raw = cv2.cvtColor(raw, cv2.COLOR_BGR2RGB)
        sky = raw[:, :, :3] * 0.8   # 稍微壓暗背景
        print(f"[renderer] 背景圖 {path} 載入成功。")
        return sky, True
    except Exception as e:
        print(f"[renderer] 背景圖讀取錯誤：{e}")
        return None, False


# ---------------------------------------------------------------------------
# 公開介面：渲染單幀
# ---------------------------------------------------------------------------
def render_frame(azimuth_deg: float,
                 resolution: int | None = None,
                 sky_img=None,
                 use_bg: bool = False) -> np.ndarray:
    """
    渲染一幀，回傳 (resolution, resolution, 3) float32 RGB [0, 1]。

    Parameters
    ----------
    azimuth_deg : 攝影機方位角（度），動畫時逐幀遞增
    resolution  : 解析度；None 時使用 config.RENDER_RESOLUTION
    sky_img     : 預先載入的背景圖（ndarray），None 時內部自動載入（單幀模式用）
    use_bg      : 是否使用背景圖
    """
    if resolution is None:
        resolution = cfg.RENDER_RESOLUTION

    r_s  = cfg.R_S
    r_in = cfg.R_IN
    r_out= cfg.R_OUT

    # --- 建立攝影機 ---
    cam = build_camera(cfg.CAM_DISTANCE, cfg.CAM_ELEVATION_DEG, azimuth_deg)
    rays_o, rays_d = generate_rays(cam, resolution, cfg.FOV_SCALE, cfg.FOCAL_LENGTH)

    N = resolution * resolution
    r = rays_o.copy()
    v = rays_d.copy()

    v_init = v.copy()
    b = compute_impact_parameter(cam.eye_pos, v_init)  # (N,) 碰撞參數

    active_mask       = np.ones(N, dtype=bool)
    accumulated_color = np.zeros((N, 3), dtype=np.float32)
    remaining_light   = np.ones((N, 1),  dtype=np.float32)

    # --- 背景：單幀模式才在這裡載入；動畫模式由外部傳入 ---
    if sky_img is None:
        sky_img, use_bg = _load_background(cfg.BACKGROUND_IMAGE_PATH)

    # 逃逸閾值：至少要比攝影機距離再遠 20%，避免光子出發就被誤判逃逸
    escape_radius = max(cfg.CAM_DISTANCE * 1.2, 60.0)

    # --- 主迴圈：RK4 光線追蹤 ---
    for _ in range(cfg.STEPS):
        r_old = r.copy()

        # 只推進 active 光子
        active_idx = np.where(active_mask)[0]
        if active_idx.size == 0:
            break

        sub_mask = np.ones(active_idx.size, dtype=bool)
        r[active_mask], v[active_mask] = rk4_step(
            r[active_mask], v[active_mask], cfg.DT, r_s, sub_mask
        )

        # --- 偵測穿越 z=0（吸積盤平面）---
        z_old = r_old[:, 2]
        z_new = r[:, 2]
        crossed = (z_old * z_new <= 0) & active_mask

        if np.any(crossed):
            # 線性插值，找出精確碰撞點
            dz = np.abs(z_old[crossed])
            tot = dz + np.abs(z_new[crossed]) + 1e-8
            f = dz / tot

            x_hit = r_old[crossed, 0] + f * (r[crossed, 0] - r_old[crossed, 0])
            y_hit = r_old[crossed, 1] + f * (r[crossed, 1] - r_old[crossed, 1])
            R_hit = np.sqrt(x_hit**2 + y_hit**2)

            in_disk = (R_hit >= r_in - 0.5) & (R_hit <= r_out + 1.0)

            if np.any(in_disk):
                cidx    = np.where(crossed)[0]
                hits_idx = cidx[in_disk]
                R_hits   = R_hit[in_disk]
                b_hits   = b[hits_idx]

                # 1. 密度 → Alpha
                density  = _disk_density(R_hits)
                alpha    = 1.0 - np.exp(-density * cfg.OPACITY_KAPPA)
                alpha_2d = alpha[:, np.newaxis]

                # 2. 相對論頻移（都卜勒 + 引力紅移）
                if cfg.ENABLE_DOPPLER or cfg.ENABLE_GRAVITATIONAL_REDSHIFT:
                    Omega = 1.0 / (R_hits ** 1.5)

                    if cfg.ENABLE_GRAVITATIONAL_REDSHIFT:
                        u_t = 1.0 / np.sqrt(np.clip(1.0 - 3.0 / R_hits, 0.01, 1.0))
                    else:
                        u_t = np.ones_like(R_hits)

                    if cfg.ENABLE_DOPPLER:
                        g = 1.0 / (u_t * (1.0 - Omega * b_hits))
                    else:
                        g = 1.0 / u_t

                    g = np.clip(g, 0.05, 8.0)
                else:
                    g = np.ones_like(R_hits)

                # 3. 發光顏色（劉維定理：亮度 ∝ g^4）
                brightness  = density * (g ** 4)
                hotness_map = np.clip(brightness * 1.2, 0, 1)
                disk_color  = _hot_colormap(hotness_map ** 1.5)

                # 4. Alpha Compositing（比爾-朗伯累積疊加）
                accumulated_color[hits_idx] += (
                    remaining_light[hits_idx] * alpha_2d * disk_color
                )
                remaining_light[hits_idx] *= (1.0 - alpha_2d)

                # 穿透力趨零時停止該光線（效能優化）
                stop = hits_idx[remaining_light[hits_idx, 0] < 0.01]
                active_mask[stop] = False

        # 終止條件
        r_mag = np.linalg.norm(r, axis=1)
        active_mask[r_mag <= r_s * 1.05]      = False   # 掉入黑洞
        active_mask[r_mag >  escape_radius]   = False   # 逃逸宇宙

    # --- 背景映射（全景等距投影） ---
    escaped = np.linalg.norm(r, axis=1) > r_s * 1.1

    if use_bg and sky_img is not None:
        img_H, img_W, _ = sky_img.shape
        v_esc  = v[escaped]
        v_norm = v_esc / np.linalg.norm(v_esc, axis=1, keepdims=True)

        theta = np.arcsin(np.clip(v_norm[:, 2], -1.0, 1.0))
        phi   = np.arctan2(v_norm[:, 0], v_norm[:, 1])

        u_tex = (0.5 + phi / (2 * np.pi) - 0.1) % 1.0
        v_tex = np.clip(0.5 + theta / np.pi - 0.05, 0, 1)

        px = np.clip((u_tex * (img_W - 1)).astype(int), 0, img_W - 1)
        py = np.clip(((1.0 - v_tex) * (img_H - 1)).astype(int), 0, img_H - 1)

        bg_colors = sky_img[py, px]
        accumulated_color[escaped] += remaining_light[escaped] * bg_colors
    else:
        accumulated_color[escaped] += remaining_light[escaped] * np.array(
            [0.0, 0.0, 0.02], dtype=np.float32
        )

    out = np.clip(accumulated_color, 0, 1).reshape((resolution, resolution, 3))
    return out.astype(np.float32)