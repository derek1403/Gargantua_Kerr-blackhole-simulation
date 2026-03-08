# =============================================================================
# video.py — 動畫合成器（序列版）
#
# 職責：
#   - 序列逐幀渲染（平行版請用 parallel_render.py）
#   - frames_to_video：將 PNG 序列合成 MP4
# =============================================================================

import os
import cv2
import numpy as np

import config as cfg
from renderer    import render_frame, _load_background
from postprocess import apply_postprocess
from camera_path import build_camera_path


def render_video(output_path: str | None = None) -> str:
    """序列渲染完整動畫並輸出為 MP4。"""
    if output_path is None:
        os.makedirs(cfg.OUTPUT_VIDEOS_DIR, exist_ok=True)
        output_path = os.path.join(cfg.OUTPUT_VIDEOS_DIR, cfg.VIDEO_OUTPUT_NAME)

    res          = cfg.VIDEO_RESOLUTION
    fps          = cfg.VIDEO_FPS
    total_frames = cfg.VIDEO_FPS * cfg.VIDEO_DURATION_SEC

    azimuths, elevations, distances = build_camera_path()

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_path, fourcc, fps, (res, res))
    if not writer.isOpened():
        raise RuntimeError("[video] 無法開啟 VideoWriter。")

    sky_img, use_bg = _load_background(cfg.BACKGROUND_IMAGE_PATH)

    print(f"[video] 序列渲染動畫")
    print(f"        解析度   : {res}×{res}  總幀數 : {total_frames}")
    print(f"        後製模式 : {cfg.POSTPROCESS_MODE}  輸出 : {output_path}")
    print()

    for i in range(total_frames):
        az   = float(azimuths[i])
        el   = float(elevations[i])
        dist = float(distances[i])

        cfg.CAM_ELEVATION_DEG = el
        cfg.CAM_DISTANCE      = dist

        print(f"  [{i+1:>4}/{total_frames}]  az={az:6.1f}°  el={el:5.1f}°  dist={dist:5.1f}",
              flush=True)

        rgb_float = render_frame(azimuth_deg=az, resolution=res,
                                 sky_img=sky_img, use_bg=use_bg)
        rgb_uint8 = (rgb_float * 255).astype(np.uint8)
        bgr_raw   = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR)
        bgr_final = apply_postprocess(bgr_raw)
        writer.write(bgr_final)

    writer.release()
    print(f"\n[video] 完成 → {output_path}")
    return output_path


def frames_to_video(frames_dir: str,
                    output_path: str | None = None,
                    fps: int | None = None) -> str:
    """將 output/frames/ 的 PNG 序列合成為 MP4。"""
    if fps is None:
        fps = cfg.VIDEO_FPS
    if output_path is None:
        os.makedirs(cfg.OUTPUT_VIDEOS_DIR, exist_ok=True)
        output_path = os.path.join(cfg.OUTPUT_VIDEOS_DIR, cfg.VIDEO_OUTPUT_NAME)

    files = sorted([
        f for f in os.listdir(frames_dir)
        if f.lower().endswith(".png")
    ])
    if not files:
        raise FileNotFoundError(f"[video] {frames_dir} 裡找不到任何 PNG 檔案。")

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
