# =============================================================================
# main.py — 入口點
#
# 用法：
#   python main.py --mode single                             # 互動預覽
#   python main.py --mode single --az 45 --el 20 --dist 50 \
#                  --res 350 --frame-id 42 \
#                  --output-dir output/frames/firsttry      # 由 parallel_render 呼叫
#   python main.py --mode video                             # 序列渲染
#   python main.py --mode frames                            # 序列批次輸出
#   python main.py --mode compile \
#                  --frames-dir  output/frames/firsttry \
#                  --output-path output/videos/firsttry.mp4 # 指定路徑合成
# =============================================================================

import argparse
import os
import cv2
import numpy as np
from multiprocessing import freeze_support

import config as cfg
from renderer    import render_frame
from postprocess import apply_postprocess
from video       import render_video, frames_to_video
from camera_path import build_camera_path


def cmd_single(args):
    az   = args.az   if args.az   is not None else cfg.CAM_AZIMUTH_DEG
    el   = args.el   if args.el   is not None else cfg.CAM_ELEVATION_DEG
    dist = args.dist if args.dist is not None else cfg.CAM_DISTANCE
    res  = args.res  if args.res  is not None else cfg.RENDER_RESOLUTION

    cfg.CAM_ELEVATION_DEG = el
    cfg.CAM_DISTANCE      = dist

    # 決定輸出目錄：優先用 --output-dir，否則用 config 預設
    out_dir = args.output_dir if args.output_dir else cfg.OUTPUT_FRAMES_DIR
    os.makedirs(out_dir, exist_ok=True)

    if args.frame_id is not None:
        out_path = os.path.join(out_dir, f"frame_{args.frame_id:04d}.png")
    else:
        out_path = os.path.join(out_dir, "preview.png")

    print(f"[main] 渲染單幀  az={az:.1f}°  el={el:.1f}°  dist={dist:.1f}  "
          f"res={res}  → {out_path}")

    rgb_float = render_frame(azimuth_deg=az, resolution=res)
    rgb_uint8 = (rgb_float * 255).astype(np.uint8)
    bgr_raw   = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR)
    bgr_final = apply_postprocess(bgr_raw)
    cv2.imwrite(out_path, bgr_final)
    print(f"[main] 已儲存 → {out_path}")


def cmd_video(args):
    render_video()


def cmd_frames(args):
    res = args.res if args.res is not None else cfg.VIDEO_RESOLUTION
    azimuths, elevations, distances = build_camera_path()
    total = len(azimuths)

    out_dir = args.output_dir if args.output_dir else cfg.OUTPUT_FRAMES_DIR
    os.makedirs(out_dir, exist_ok=True)
    print(f"[main] 序列批次渲染 {total} 幀 → {out_dir}")

    for i in range(total):
        cfg.CAM_ELEVATION_DEG = float(elevations[i])
        cfg.CAM_DISTANCE      = float(distances[i])

        print(f"  [{i+1:>4}/{total}]  az={azimuths[i]:6.1f}°  "
              f"el={elevations[i]:5.1f}°  dist={distances[i]:5.1f}", flush=True)

        rgb_float = render_frame(azimuth_deg=float(azimuths[i]), resolution=res)
        rgb_uint8 = (rgb_float * 255).astype(np.uint8)
        bgr_raw   = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2BGR)
        bgr_final = apply_postprocess(bgr_raw)
        cv2.imwrite(os.path.join(out_dir, f"frame_{i:04d}.png"), bgr_final)

    print(f"\n[main] 所有幀已儲存至 {out_dir}")


def cmd_compile(args):
    # frames_dir 與 output_path 可由 parallel_render 傳入，也可用預設值
    frames_dir  = args.frames_dir  if args.frames_dir  else cfg.OUTPUT_FRAMES_DIR
    output_path = args.output_path if args.output_path else None
    frames_to_video(frames_dir, output_path)


def main():
    parser = argparse.ArgumentParser(
        description="kerr-blackhole-sim — 廣義相對論黑洞渲染器"
    )
    parser.add_argument(
        "--mode", choices=["single", "video", "frames", "compile"],
        default="single"
    )
    parser.add_argument("--az",          type=float, default=None, help="方位角 (度)")
    parser.add_argument("--el",          type=float, default=None, help="仰角 (度)")
    parser.add_argument("--dist",        type=float, default=None, help="攝影機距離")
    parser.add_argument("--res",         type=int,   default=None, help="渲染解析度")
    parser.add_argument("--post",        type=str,   default=None, help="後製模式 (none/mode1/mode2)")
    parser.add_argument("--frame-id",    type=int,   default=None, dest="frame_id",
                        help="幀序號（由 parallel_render.py 傳入）")
    parser.add_argument("--output-dir",  type=str,   default=None, dest="output_dir",
                        help="single/frames 模式的輸出目錄（覆蓋 config.OUTPUT_FRAMES_DIR）")
    parser.add_argument("--frames-dir",  type=str,   default=None, dest="frames_dir",
                        help="compile 模式的 PNG 來源目錄")
    parser.add_argument("--output-path", type=str,   default=None, dest="output_path",
                        help="compile 模式的影片輸出完整路徑")

    args = parser.parse_args()

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
    freeze_support()
    main()
