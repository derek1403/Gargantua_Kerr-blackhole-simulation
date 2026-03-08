# =============================================================================
# camera.py — 虛擬攝影機
#
# 職責：純幾何運算。給定仰角/方位角，建構攝影機座標系，
#        並將 2D 像素座標轉換為 3D 初始射線方向。
#
# 不依賴 config 以外的任何模組，方便單獨測試。
# =============================================================================

from __future__ import annotations
import numpy as np
from dataclasses import dataclass


@dataclass
class Camera:
    """
    封裝攝影機的所有幾何資訊。

    Attributes
    ----------
    eye_pos : (3,)  攝影機在世界座標的位置
    forward : (3,)  攝影機朝向（單位向量，指向黑洞）
    right   : (3,)  攝影機右方（單位向量）
    up      : (3,)  攝影機正上方（單位向量）
    """
    eye_pos: np.ndarray
    forward: np.ndarray
    right:   np.ndarray
    up:      np.ndarray


def build_camera(distance: float,
                 elevation_deg: float,
                 azimuth_deg: float) -> Camera:
    """
    透過球座標建立攝影機，自動計算 Forward/Right/Up 三個基底向量。

    比喻：就像在黑洞周圍掛了一顆衛星，
    你只需要告訴它「高度角」和「繞了幾度」，
    它就能算出自己面朝哪裡、頭頂朝哪裡。

    Parameters
    ----------
    distance      : 攝影機與黑洞的距離
    elevation_deg : 仰角（度），0 = 赤道面，90 = 正上方
    azimuth_deg   : 方位角（度），控制繞行方向

    Returns
    -------
    Camera dataclass
    """
    elev = np.radians(elevation_deg)
    azim = np.radians(azimuth_deg)

    # 球座標 → 直角座標
    cx = distance * np.cos(elev) * np.sin(azim)
    cy = -distance * np.cos(elev) * np.cos(azim)
    cz = distance * np.sin(elev)
    eye_pos = np.array([cx, cy, cz], dtype=np.float64)

    # Forward：從攝影機指向原點
    forward = -eye_pos / np.linalg.norm(eye_pos)

    # Right：Forward × WorldUp，確保不與 Forward 平行
    world_up = np.array([0.0, 0.0, 1.0])
    right = np.cross(forward, world_up)
    right_norm = np.linalg.norm(right)
    if right_norm < 1e-8:
        # 正對極點時退化，改用 x 軸
        world_up = np.array([1.0, 0.0, 0.0])
        right = np.cross(forward, world_up)
        right_norm = np.linalg.norm(right)
    right /= right_norm

    # Up：由 Right × Forward 重新正交化，保證嚴格垂直
    up = np.cross(right, forward)

    return Camera(eye_pos=eye_pos, forward=forward, right=right, up=up)


def generate_rays(cam: Camera,
                  resolution: int,
                  fov_scale: float,
                  focal_length: float) -> tuple[np.ndarray, np.ndarray]:
    """
    將螢幕上的每個像素轉換為 3D 射線。

    公式：d = focal_length * forward + u * right + v * up
    最後正規化成單位向量。

    Parameters
    ----------
    cam          : Camera dataclass
    resolution   : 渲染解析度（正方形，pixel）
    fov_scale    : 視野縮放（控制畫面涵蓋多大的空間範圍）
    focal_length : 等效焦距（越大視角越窄）

    Returns
    -------
    rays_o : (N, 3) 射線起點（全部等於 eye_pos）
    rays_d : (N, 3) 射線方向（已正規化）
    """
    u_coords = np.linspace(-fov_scale,  fov_scale, resolution)
    v_coords = np.linspace( fov_scale, -fov_scale, resolution)  # 注意上下翻轉
    U, V = np.meshgrid(u_coords, v_coords)

    u_flat = U.ravel()[:, np.newaxis]  # (N, 1)
    v_flat = V.ravel()[:, np.newaxis]  # (N, 1)

    # 每條射線 = 焦距方向 + 橫向偏移 + 縱向偏移
    dirs = (focal_length * cam.forward
            + u_flat * cam.right
            + v_flat * cam.up)

    # 正規化
    norms = np.linalg.norm(dirs, axis=1, keepdims=True)
    rays_d = dirs / norms

    N = resolution * resolution
    rays_o = np.tile(cam.eye_pos, (N, 1))

    return rays_o, rays_d