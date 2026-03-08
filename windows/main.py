print('hi')
# =============================================================================
# main.py — 入口點
#
# 用法：
#   python main.py --mode single              # 渲染單幀，快速預覽
#   python main.py --mode video               # 渲染完整動畫
#   python main.py --mode frames              # 批次輸出所有單幀 PNG
#   python main.py --mode compile             # 將 frames/ 合成影片（不重跑物理）
#
# 常用覆蓋參數（不用改 config.py）：
#   --az    90.0     # 指定單幀的方位角
#   --res   600      # 覆蓋解析度
#   --post  mode1    # 覆蓋後製模式
# =============================================================================

import argparse
import os
import cv2
import numpy as np

import config as cfg
from renderer    import render_frame
from postprocess import apply_postprocess
from video       import render_video, frames_to_video


# ---------------------------------------------------------------------------
# 子命令：single
# ---------------------------------------------------------------------------
def cmd_single(args):
    az  = args.az  if args.az  is not None else cfg.CAM_AZIMUTH_DEG
    res = args.res if args.res is not None else cfg.RENDER_RESOLUTION

    print(f"[main] 渲染單幀  方位角={az}°  解析度={res}")
    rgb_float = render_frame(azimuth_deg=az, resolution=res)

    rgb_uint8 = (rgb_float * 255).astype(np.uint8)
    bgr_raw   = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR)
    bgr_final = apply_postprocess(bgr_raw)

    os.makedirs(cfg.OUTPUT_FRAMES_DIR, exist_ok=True)
    out_path = os.path.join(cfg.OUTPUT_FRAMES_DIR, "preview.png")
    cv2.imwrite(out_path, bgr_final)
    print(f"[main] 已儲存 → {out_path}")


# ---------------------------------------------------------------------------
# 子命令：video
# ---------------------------------------------------------------------------
def cmd_video(args):
    render_video()


# ---------------------------------------------------------------------------
# 子命令：frames（批次輸出每一幀為獨立 PNG，方便後續逐幀調整後製）
# ---------------------------------------------------------------------------
def cmd_frames(args):
    total   = cfg.VIDEO_FPS * cfg.VIDEO_DURATION_SEC
    az_s    = cfg.VIDEO_AZIMUTH_START
    az_e    = cfg.VIDEO_AZIMUTH_END
    res     = args.res if args.res is not None else cfg.VIDEO_RESOLUTION

    os.makedirs(cfg.OUTPUT_FRAMES_DIR, exist_ok=True)
    print(f"[main] 批次渲染 {total} 幀 → {cfg.OUTPUT_FRAMES_DIR}")

    for i in range(total):
        az  = az_s + (i / total) * (az_e - az_s)
        print(f"  幀 {i+1:>4}/{total}  方位角 {az:6.1f}°", end="\r", flush=True)

        rgb_float = render_frame(azimuth_deg=az, resolution=res)
        rgb_uint8 = (rgb_float * 255).astype(np.uint8)
        bgr_raw   = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR)
        bgr_final = apply_postprocess(bgr_raw)

        fname = os.path.join(cfg.OUTPUT_FRAMES_DIR, f"frame_{i:04d}.png")
        cv2.imwrite(fname, bgr_final)

    print(f"\n[main] 所有幀已儲存至 {cfg.OUTPUT_FRAMES_DIR}")


# ---------------------------------------------------------------------------
# 子命令：compile（frames/ → mp4，無需重跑物理）
# ---------------------------------------------------------------------------
def cmd_compile(args):
    frames_to_video(cfg.OUTPUT_FRAMES_DIR)


# ---------------------------------------------------------------------------
# CLI 解析
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="kerr-blackhole-sim — 廣義相對論黑洞渲染器"
    )
    parser.add_argument(
        "--mode", choices=["single", "video", "frames", "compile"],
        default="single",
        help="執行模式：single=單幀預覽 | video=直接渲染動畫 | "
             "frames=批次輸出PNG | compile=合成影片"
    )
    parser.add_argument("--az",   type=float, default=None,
                        help="單幀方位角 (度)，覆蓋 config.CAM_AZIMUTH_DEG")
    parser.add_argument("--res",  type=int,   default=None,
                        help="覆蓋渲染解析度")
    parser.add_argument("--post", type=str,   default=None,
                        help="覆蓋後製模式 (none/mode1/mode2)")

    args = parser.parse_args()

    # 動態覆蓋 config（不用改檔案）
    if args.post is not None:
        cfg.POSTPROCESS_MODE = args.post

    dispatch = {
        "single" : cmd_single,
        "video"  : cmd_video,
        "frames" : cmd_frames,
        "compile": cmd_compile,
    }
    dispatch[args.mode](args)


if __name__ == "__main__":
    main()