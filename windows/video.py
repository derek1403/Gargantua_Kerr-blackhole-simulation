# =============================================================================
# video.py — 動畫合成器
#
# 職責：
#   - 根據 config 計算總幀數與每幀的方位角
#   - 逐幀呼叫 renderer.render_frame + postprocess.apply_postprocess
#   - 用 OpenCV VideoWriter 寫入 .mp4
#
# 與渲染邏輯完全解耦，若只想換後製效果，只需改 config.POSTPROCESS_MODE。
# =============================================================================

import os
import cv2
import numpy as np

import config as cfg
from renderer     import render_frame
from postprocess  import apply_postprocess
from camera_path  import build_camera_path


def render_video(output_path: str | None = None) -> str:
    """
    渲染完整動畫並輸出為 MP4。

    Parameters
    ----------
    output_path : 輸出路徑；None 時使用
                  config.OUTPUT_VIDEOS_DIR / config.VIDEO_OUTPUT_NAME

    Returns
    -------
    str : 最終輸出路徑
    """
    # --- 輸出路徑 ---
    if output_path is None:
        os.makedirs(cfg.OUTPUT_VIDEOS_DIR, exist_ok=True)
        output_path = os.path.join(cfg.OUTPUT_VIDEOS_DIR, cfg.VIDEO_OUTPUT_NAME)

    res          = cfg.VIDEO_RESOLUTION
    fps          = cfg.VIDEO_FPS
    total_frames = cfg.VIDEO_FPS * cfg.VIDEO_DURATION_SEC

    # --- 建立攝影機路徑 ---
    azimuths, elevations, distances = build_camera_path()

    # --- 初始化 VideoWriter ---
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps, (res, res))

    if not writer.isOpened():
        raise RuntimeError(f"[video] 無法開啟 VideoWriter，請確認 OpenCV 支援 mp4v 編碼。")

    # --- 預先載入背景圖（只讀一次）---
    from renderer import _load_background
    sky_img, use_bg = _load_background(cfg.BACKGROUND_IMAGE_PATH)

    print(f"[video] 開始渲染動畫")
    print(f"        解析度  : {res}×{res}")
    print(f"        總幀數  : {total_frames}  ({fps} fps × {cfg.VIDEO_DURATION_SEC} s)")
    print(f"        緩動    : {cfg.CAMERA_EASING}")
    print(f"        後製模式: {cfg.POSTPROCESS_MODE}")
    print(f"        輸出    : {output_path}")
    print()

    for i in range(total_frames):
        az   = azimuths[i]
        el   = elevations[i]
        dist = distances[i]

        print(f"  [{i+1:>4}/{total_frames}]  az={az:6.1f}°  el={el:5.1f}°  dist={dist:5.1f}",
              flush=True)

        # 動態覆蓋 config 裡的攝影機距離與仰角
        cfg.CAM_ELEVATION_DEG = el
        cfg.CAM_DISTANCE      = dist

        # 1. 物理渲染 → float32 RGB [0,1]（背景圖由外部傳入，不重複讀檔）
        rgb_float = render_frame(azimuth_deg=az, resolution=res,
                                 sky_img=sky_img, use_bg=use_bg)

        # 2. 轉成 uint8 BGR（OpenCV 慣例）
        rgb_uint8 = (rgb_float * 255).astype(np.uint8)
        bgr_raw   = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR)

        # 3. 後製
        bgr_final = apply_postprocess(bgr_raw)

        # 4. 寫入影片
        writer.write(bgr_final)

    writer.release()
    print(f"\n[video] 動畫渲染完成 → {output_path}")
    return output_path


def frames_to_video(frames_dir: str,
                    output_path: str | None = None,
                    fps: int | None = None) -> str:
    """
    將 output/frames/ 目錄下的 PNG 序列合成成影片。
    適合「先批次渲染單幀、再合成」的工作流程。

    Parameters
    ----------
    frames_dir  : 含有 frame_XXXX.png 的目錄
    output_path : 輸出影片路徑
    fps         : 幀率；None 時使用 config.VIDEO_FPS

    Returns
    -------
    str : 輸出路徑
    """
    if fps is None:
        fps = cfg.VIDEO_FPS
    if output_path is None:
        os.makedirs(cfg.OUTPUT_VIDEOS_DIR, exist_ok=True)
        output_path = os.path.join(cfg.OUTPUT_VIDEOS_DIR, cfg.VIDEO_OUTPUT_NAME)

    # 取得所有 PNG，排序確保順序正確
    files = sorted([
        f for f in os.listdir(frames_dir)
        if f.lower().endswith(".png")
    ])

    if not files:
        raise FileNotFoundError(f"[video] {frames_dir} 裡找不到任何 PNG 檔案。")

    # 取第一張圖決定解析度
    sample = cv2.imread(os.path.join(frames_dir, files[0]))
    h, w   = sample.shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps, (w, h))

    print(f"[video] 合成 {len(files)} 幀 ({w}×{h}) → {output_path}")

    for fname in files:
        frame = cv2.imread(os.path.join(frames_dir, fname))
        writer.write(frame)

    writer.release()
    print(f"[video] 合成完成 → {output_path}")
    return output_path