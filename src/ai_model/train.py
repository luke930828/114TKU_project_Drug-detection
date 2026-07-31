"""
YOLO 訓練腳本 (16 類別 / v2)

用法：
    python -m src.ai_model.train

訓練資料預設讀 data/processed/data.yaml（由 src/ai_model/import_roboflow.py 匯入 Roboflow 標註產生）。
訓練完成後，會自動把這次跑出來的 best.pt 複製到 models/best.pt —— 也就是 api_server.py 實際載入推論用的那份權重。
"""

import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import torch
from ultralytics import YOLO

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class TrainConfig:
    base_model: str = "models/yolo11n.pt"      # 訓練起點的基礎模型
    data_yaml: str = "data/processed/data.yaml"  # 16 類別訓練資料清單
    epochs: int = 50
    imgsz: int = 640
    batch: int = 16                             # 3050 Ti 若記憶體不足可調成 8
    device: Union[int, str] = field(default_factory=lambda: 0 if torch.cuda.is_available() else "cpu")
    project: str = "runs/detect"                # 訓練紀錄輸出的根目錄
    name: str = "drug_prevention_v2"            # 這次實驗的名稱
    exist_ok: bool = True                       # 名稱重複時直接覆蓋
    deploy_dir: Path = Path("models")           # 最終權重要部署到哪個資料夾
    deploy_filename: str = "best.pt"            # api_server.py 實際載入的檔名


def describe_device(device: Union[int, str]) -> str:
    return f"NVIDIA GPU (device={device})" if device != "cpu" else "CPU（訓練時間會長很多）"


def backup_existing_weights(dest: Path) -> None:
    if not dest.exists():
        return
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = dest.with_name(f"{dest.stem}_backup_{timestamp}{dest.suffix}")
    shutil.move(str(dest), str(backup_path))
    print(f"🗂️ 偵測到既有的 {dest.name}，已備份至: {backup_path}")


def deploy_weights(source: Path, config: TrainConfig) -> Path:
    if not source.exists():
        raise FileNotFoundError(f"找不到訓練產出的權重檔: {source}")

    config.deploy_dir.mkdir(parents=True, exist_ok=True)
    dest = config.deploy_dir / config.deploy_filename

    backup_existing_weights(dest)
    shutil.copy2(source, dest)
    return dest


def print_training_banner(config: TrainConfig) -> None:
    print("=" * 60)
    print("🚀 [訓練啟動] 防毒影像辨識模型 - 16 類別訓練流程")
    print(f"   基礎模型   : {config.base_model}")
    print(f"   訓練資料   : {config.data_yaml}")
    print(f"   Epochs     : {config.epochs}")
    print(f"   Batch Size : {config.batch}")
    print(f"   Image Size : {config.imgsz}")
    print(f"   運算裝置   : {describe_device(config.device)}")
    print(f"   實驗紀錄   : {config.project}/{config.name}")
    print("=" * 60)


def print_training_summary(final_weights_path: Path, run_dir: Path, metrics, data_yaml: str) -> None:
    print("\n" + "=" * 60)
    print("✅ [訓練完成] 模型已成功訓練並部署！")
    print(f"   最終權重已儲存至 : {final_weights_path.resolve()}")
    print(f"   訓練紀錄與圖表   : {run_dir.resolve()}")

    results_dict = getattr(metrics, "results_dict", None) if metrics is not None else None
    if results_dict:
        map50 = results_dict.get("metrics/mAP50(B)")
        map50_95 = results_dict.get("metrics/mAP50-95(B)")
        if map50 is not None:
            print(f"   評估結果         : mAP50 = {map50:.4f}, mAP50-95 = {map50_95:.4f}")
    else:
        print("   評估結果         : 未取得驗證指標，可自行執行下方指令補跑驗證")

    print(f"   👉 建議驗證指令   : yolo val model={final_weights_path} data={data_yaml}")
    print("=" * 60)


def train_model(config: TrainConfig = None) -> Path:
    config = config or TrainConfig()

    print_training_banner(config)

    model = YOLO(config.base_model)
    metrics = model.train(
        data=config.data_yaml,
        epochs=config.epochs,
        imgsz=config.imgsz,
        batch=config.batch,
        device=config.device,
        project=config.project,
        name=config.name,
        exist_ok=config.exist_ok,
    )

    trainer = model.trainer
    weights_source = trainer.best if trainer.best.exists() else trainer.last
    final_weights_path = deploy_weights(weights_source, config)

    print_training_summary(final_weights_path, trainer.save_dir, metrics, config.data_yaml)
    return final_weights_path


if __name__ == "__main__":
    train_model()
