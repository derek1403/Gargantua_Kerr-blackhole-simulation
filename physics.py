# =============================================================================
# physics.py — 物理核心
#
# 職責：只處理「光子在彎曲時空中如何運動」，不碰任何渲染或 I/O。
#
# 核心公式（史瓦西度規，自然單位 G=M=c=1）：
#   引力加速度： a = -1.5 * r_s * h² / |r|⁵ * r
#   其中 h = r × v 為守恆角動量向量
# =============================================================================

import numpy as np


def _gravity_acceleration(r: np.ndarray, v: np.ndarray,
                           r_s: float, mask: np.ndarray) -> np.ndarray:
    """
    計算批次光子的引力加速度。

    Parameters
    ----------
    r    : (N, 3) 位置向量
    v    : (N, 3) 速度向量
    r_s  : float  史瓦西半徑
    mask : (N,) bool  只計算 mask=True 的光子

    Returns
    -------
    ax : (N, 3) 加速度向量（mask=False 的列保持零）
    """
    N = r.shape[0]
    ax = np.zeros((N, 3), dtype=np.float64)

    r_mag = np.linalg.norm(r, axis=1, keepdims=True)          # (N, 1)
    valid = mask & (r_mag[:, 0] > 1e-4)

    if not np.any(valid):
        return ax

    rv = r[valid]
    vv = v[valid]
    rm = r_mag[valid]                                          # (M, 1)

    h_vec = np.cross(rv, vv)                                   # (M, 3)
    h_sq  = np.sum(h_vec ** 2, axis=1, keepdims=True)         # (M, 1)

    coef = -1.5 * r_s * h_sq / (rm ** 5)                      # (M, 1)
    ax[valid] = coef * rv
    return ax


def get_derivatives(r: np.ndarray, v: np.ndarray,
                    r_s: float, mask: np.ndarray):
    """
    回傳 (dr/dt, dv/dt)，供 RK4 使用。
    """
    return v, _gravity_acceleration(r, v, r_s, mask)


def rk4_step(r: np.ndarray, v: np.ndarray,
             dt: float, r_s: float, mask: np.ndarray):
    """
    四階龍格-庫塔法，推進一個時間步。

    比喻：相當於在每一個 dt 內「向前試探四個方向」，
    取加權平均斜率，避免在光子球附近的極端彎曲軌跡
    因為步長累積誤差而失控。

    Parameters
    ----------
    r, v  : (N, 3) 當前位置與速度
    dt    : 積分步長
    r_s   : 史瓦西半徑
    mask  : (N,) bool，只更新 active 的光子

    Returns
    -------
    r_new, v_new : (N, 3)
    """
    v1, a1 = get_derivatives(r,                   v,                   r_s, mask)
    v2, a2 = get_derivatives(r + 0.5*dt*v1,       v + 0.5*dt*a1,       r_s, mask)
    v3, a3 = get_derivatives(r + 0.5*dt*v2,       v + 0.5*dt*a2,       r_s, mask)
    v4, a4 = get_derivatives(r +    dt*v3,         v +    dt*a3,         r_s, mask)

    r_new = r + (dt / 6.0) * (v1 + 2*v2 + 2*v3 + v4)
    v_new = v + (dt / 6.0) * (a1 + 2*a2 + 2*a3 + a4)
    return r_new, v_new


def compute_impact_parameter(eye_pos: np.ndarray,
                              v_init: np.ndarray) -> np.ndarray:
    """
    計算每條光線的守恆碰撞參數 b。

    b 決定光子打在畫面左邊還是右邊，也是計算都卜勒頻移的關鍵輸入。
    公式：b = -(x_cam * vy - y_cam * vx)

    Parameters
    ----------
    eye_pos : (3,) 攝影機世界座標
    v_init  : (N, 3) 初始光線方向（已正規化）

    Returns
    -------
    b : (N,) 碰撞參數
    """
    return -(eye_pos[0] * v_init[:, 1] - eye_pos[1] * v_init[:, 0])