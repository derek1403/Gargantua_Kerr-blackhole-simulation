# =============================================================================
# parallel_render.py — 平行渲染調配器
#
# 用法：
#   python parallel_render.py                        # 時間戳命名資料夾
#   python parallel_render.py --name firsttry        # 指定資料夾名稱
#   python parallel_render.py --workers 6            # 限制 worker 數
#   python parallel_render.py --dry-run              # 只印指令不執行
#   python parallel_render.py --no-compile           # 不自動合成影片
#   python parallel_render.py --retry-failed --name firsttry  # 補跑缺幀
# =============================================================================

import argparse
import os
import sys
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import config as cfg
from camera_path import build_camera_path


def _run_single_frame(cmd: list[str], frame_id: int, total: int) -> tuple[int, bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=None) # 不設 timeout，讓子程序自己決定何時結束 或者可以設置一個合理的 timeout，例如 600 秒，避免無限掛起
        if result.returncode == 0:
            return frame_id, True, ""
        else:
            return frame_id, False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return frame_id, False, "TIMEOUT"
    except Exception as e:
        return frame_id, False, str(e)


def main():
    parser = argparse.ArgumentParser(
        description="平行渲染調配器"
    )
    parser.add_argument("--name",         type=str,  default=None,
                        help="輸出子資料夾名稱；未指定則用時間戳 (20260308_2235)")
    parser.add_argument("--workers",      type=int,  default=None,
                        help="同時執行的 subprocess 數；預設 = CPU 核心數")
    parser.add_argument("--dry-run",      action="store_true",
                        help="只印出將執行的指令，不實際渲染")
    parser.add_argument("--no-compile",   action="store_true",
                        help="渲染完後不自動合成影片")
    parser.add_argument("--retry-failed", action="store_true",
                        help="只重跑缺少的幀，跳過已存在的")
    args = parser.parse_args()

    # --- 決定輸出子資料夾 ---
    folder_name = args.name if args.name else datetime.now().strftime("%Y%m%d_%H%M")
    frames_dir  = os.path.join(cfg.OUTPUT_FRAMES_DIR, folder_name)
    os.makedirs(frames_dir, exist_ok=True)

    # --- 準備參數 ---
    azimuths, elevations, distances = build_camera_path()
    total   = len(azimuths)
    res     = cfg.VIDEO_RESOLUTION
    n_cpu   = os.cpu_count() or 1
    workers = args.workers or cfg.VIDEO_MAX_WORKERS or n_cpu
    python  = sys.executable

    # --- 建立工作清單 ---
    tasks   = []
    skipped = 0
    for i in range(total):
        out_file = os.path.join(frames_dir, f"frame_{i:04d}.png")
        if args.retry_failed and os.path.exists(out_file):
            skipped += 1
            continue
        cmd = [
            python, "main.py",
            "--mode",       "single",
            "--az",         f"{azimuths[i]:.6f}",
            "--el",         f"{elevations[i]:.6f}",
            "--dist",       f"{distances[i]:.6f}",
            "--res",        str(res),
            "--frame-id",   str(i),
            "--output-dir", frames_dir,   # ← 告訴 main.py 存到哪個子資料夾
        ]
        tasks.append((i, cmd))

    print(f"[parallel] kerr-blackhole-sim 平行渲染")
    print(f"           資料夾  : {frames_dir}")
    print(f"           總幀數  : {total}  待渲染 : {len(tasks)}  跳過 : {skipped}")
    print(f"           Workers : {workers} / {n_cpu} cores  解析度 : {res}×{res}")
    print()

    if args.dry_run:
        print("[dry-run] 前 5 條指令預覽：")
        for i, cmd in tasks[:5]:
            print(f"  {' '.join(cmd)}")
        if len(tasks) > 5:
            print(f"  ... 共 {len(tasks)} 條")
        return

    if not tasks:
        print("[parallel] 沒有需要渲染的幀，直接合成。")
    else:
        failed_frames = []
        done          = 0
        start_time    = datetime.now()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_single_frame, cmd, i, total): i
                for i, cmd in tasks
            }
            for fut in as_completed(futures):
                frame_id, success, err = fut.result()
                done   += 1
                elapsed = (datetime.now() - start_time).total_seconds()
                eta     = elapsed / done * (len(tasks) - done) if done < len(tasks) else 0

                if success:
                    print(f"  [{done:>4}/{len(tasks)}] 幀 {frame_id:>4} ✓  "
                          f"已用 {elapsed:5.1f}s  預估剩餘 {eta:5.1f}s", flush=True)
                else:
                    print(f"  [{done:>4}/{len(tasks)}] 幀 {frame_id:>4} ✗  {err}", flush=True)
                    failed_frames.append(frame_id)

        print()
        if failed_frames:
            print(f"[parallel] ⚠️  {len(failed_frames)} 幀失敗：{failed_frames}")
            print(f"           重跑：python parallel_render.py --name {folder_name} --retry-failed")
        else:
            print(f"[parallel] 所有幀完成 ✓")

    # --- 合成影片 ---
    if not args.no_compile:
        # 影片命名與資料夾同名
        video_name  = f"{folder_name}.mp4"
        output_path = os.path.join(cfg.OUTPUT_VIDEOS_DIR, video_name)
        print(f"\n[parallel] 合成影片 → {output_path}")
        result = subprocess.run(
            [python, "main.py", "--mode", "compile",
             "--frames-dir",  frames_dir,
             "--output-path", output_path],
            capture_output=False
        )
        if result.returncode != 0:
            print("[parallel] ⚠️  影片合成失敗")


if __name__ == "__main__":
    main()
