# =============================================================================
# postprocess.py — 電影級後製管線
#
# 職責：接收 uint8 BGR 影像，套用後製，回傳 uint8 BGR 影像。
#       不依賴 physics / camera / renderer，可單獨對靜態圖片使用。
#
# 兩種模式：
#   Mode 1 — 均勻曝光 + Gamma + Bloom + 暖色調（快速、穩定）
#   Mode 2 — 高光遮罩選擇性曝光 + Selective Bloom（更電影感）
# =============================================================================

import cv2
import numpy as np
import config as cfg


# ---------------------------------------------------------------------------
# Mode 1：均勻曝光
# ---------------------------------------------------------------------------
def postprocess_mode1(img_bgr: np.ndarray) -> np.ndarray:
    """
    參數全部來自 config.MODE1_*。

    流程：
      曝光增益 → Gamma 校正 → 全域 Bloom → 對比度調整 → 暖色偏移
    """
    img = img_bgr.astype(np.float32) / 255.0

    # 1. 曝光（線性亮度縮放）
    img = np.clip(img * cfg.MODE1_EXPOSURE, 0, 1)

    # 2. Gamma 校正（<1 提亮中間調，類似 PS Gamma）
    img = img ** cfg.MODE1_GAMMA

    # 3. 全域 Bloom（高斯模糊疊加）
    sigma = cfg.MODE1_BLOOM_SIGMA
    blur  = cv2.GaussianBlur(img, (0, 0), sigma)
    img   = cv2.addWeighted(img, 1.0, blur, cfg.MODE1_BLOOM_MIX, 0)

    # 4. 對比度調整（繞 0.5 灰做線性縮放）
    img = (img - 0.5) * cfg.MODE1_CONTRAST + 0.5

    # 5. 暖色偏移（增紅、減藍）
    b, g, r = cv2.split(img)
    r = r * (1 + cfg.MODE1_WARM)
    b = b * (1 - cfg.MODE1_WARM * 0.7)
    img = cv2.merge([b, g, r])

    img = np.clip(img, 0, 1)
    return (img * 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Mode 2：高光限定曝光 + Selective Bloom
# ---------------------------------------------------------------------------
def postprocess_mode2(img_bgr: np.ndarray) -> np.ndarray:
    """
    參數全部來自 config.MODE2_*。

    流程：
      感知亮度 → 高光遮罩（非線性次方） →
      選擇性曝光（只炸亮部） → Selective Bloom → 對比度微調

    比喻：普通曝光是把整個房間的燈全開，
          Mode 2 是只把「蠟燭火焰」的部分放大，
          讓暗部保持神秘、亮部產生電影般的光暈。
    """
    img = img_bgr.astype(np.float32) / 255.0

    # 1. 感知亮度（ITU-R BT.601 加權，OpenCV BGR 順序）
    b_ch, g_ch, r_ch = cv2.split(img)
    luminance = 0.299 * r_ch + 0.587 * g_ch + 0.114 * b_ch

    # 2. 高光遮罩（次方越大 = 只針對最亮的區域）
    mask    = luminance ** cfg.MODE2_HIGHLIGHT_POWER
    mask_3d = np.stack([mask, mask, mask], axis=-1)

    # 3. 選擇性曝光：基礎亮度 + 高光區額外增幅
    img = np.clip(
        img * cfg.MODE2_BASE_EXPOSURE + img * mask_3d * cfg.MODE2_HIGH_BOOST,
        0, 1
    )

    # 4. Selective Bloom（只對高光區域做模糊）
    highlights = img * mask_3d
    sigma      = cfg.MODE2_BLOOM_SIGMA
    blur       = cv2.GaussianBlur(highlights, (0, 0), sigma)
    img        = cv2.addWeighted(img, 1.0, blur, cfg.MODE2_GLOW_INTENSITY, 0)

    # 5. 對比度微調
    img = np.clip((img - 0.5) * cfg.MODE2_CONTRAST + 0.5, 0, 1)

    return (img * 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# 公開介面：根據 config 自動分派
# ---------------------------------------------------------------------------
def apply_postprocess(img_bgr: np.ndarray) -> np.ndarray:
    """
    根據 config.POSTPROCESS_MODE 自動選擇後製模式。

    Parameters
    ----------
    img_bgr : uint8 BGR 影像（OpenCV 格式）

    Returns
    -------
    uint8 BGR 後製結果；若 mode="none" 則原樣回傳
    """
    mode = cfg.POSTPROCESS_MODE.lower()

    if mode == "mode1":
        return postprocess_mode1(img_bgr)
    elif mode == "mode2":
        return postprocess_mode2(img_bgr)
    elif mode == "none":
        return img_bgr
    else:
        raise ValueError(
            f"[postprocess] 未知的 POSTPROCESS_MODE='{cfg.POSTPROCESS_MODE}'，"
            f"請設為 'none'、'mode1' 或 'mode2'。"
        )


# ---------------------------------------------------------------------------
# 單獨對靜態圖片使用（CLI）
# ---------------------------------------------------------------------------
def process_single_image(input_path: str, output_path: str) -> None:
    """
    對單張靜態圖片套用後製並存檔。
    可直接 python postprocess.py input.png output.png 使用。
    """
    img = cv2.imread(input_path)
    if img is None:
        raise FileNotFoundError(f"[postprocess] 找不到圖片：{input_path}")

    result = apply_postprocess(img)
    cv2.imwrite(output_path, result)
    print(f"[postprocess] 後製完成，儲存至 {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3:
        process_single_image(sys.argv[1], sys.argv[2])
    else:
        print("用法：python postprocess.py <input.png> <output.png>")