# kerr-blackhole-sim

廣義相對論黑洞渲染器。把愛因斯坦場方程轉化為電影級 3D 動畫。

## 專案結構

```
kerr-blackhole-sim/
├── assets/
│   └── galaxy.png          # 背景星空（全景等距投影）
├── output/
│   ├── frames/             # 單幀 PNG 輸出
│   └── videos/             # 動畫 MP4 輸出
│
├── config.py               # ⚙️ 所有參數與開關
├── physics.py              # 🔭 測地線方程 + RK4 積分器
├── camera.py               # 📷 虛擬攝影機 + 光線生成
├── renderer.py             # 🌌 主渲染引擎（光線追蹤 + Alpha 合成）
├── postprocess.py          # 🎬 後製管線（Mode 1 / Mode 2）
├── video.py                # 🎥 動畫合成器
└── main.py                 # 🚀 入口點
```

## 安裝

```bash
pip install numpy opencv-python
```

## 快速開始

```bash
# 渲染單幀預覽（最快）
python main.py --mode single

# 指定方位角 + 高解析度
python main.py --mode single --az 45 --res 800

# 渲染完整動畫
python main.py --mode video

# 先批次輸出 PNG，再合成（適合調整後製時不用重跑物理）
python main.py --mode frames
python main.py --mode compile

# 直接對靜態圖片套後製
python postprocess.py input.png output.png
```

## config.py 主要開關速查

| 參數 | 預設 | 說明 |
|------|------|------|
| `ENABLE_DOPPLER` | `True` | 都卜勒頻移（左亮右暗） |
| `ENABLE_GRAVITATIONAL_REDSHIFT` | `True` | 引力時間膨脹 |
| `ENABLE_BACKGROUND_IMAGE` | `True` | 背景星空；`False` 改純黑 |
| `ENABLE_DISK_GAPS` | `True` | 吸積盤主要間隙 |
| `ENABLE_SMALL_GAPS` | `True` | 微小縫隙 |
| `ENABLE_RIPPLES` | `True` | sin 波紋紋理 |
| `ENABLE_EDGE_FALLOFF` | `True` | 邊緣平滑衰減 |
| `POSTPROCESS_MODE` | `"mode2"` | `"none"` / `"mode1"` / `"mode2"` |

## 物理說明

- **度規**：史瓦西（Schwarzschild），自然單位 $G=M=c=1$
- **光線追蹤**：四階 RK4 數值積分測地線方程
- **吸積盤**：體積光線追蹤 + Beer-Lambert Alpha 合成
- **相對論效應**：都卜勒頻移 + 引力紅移（劉維定理 $I \propto g^4$）
- **下一步**：升級至 Kerr 度規，加入參考系拖曳（frame-dragging）