"""
Fine-tuning script for JanVedha civic complaint classifier.

Takes synthetic (or real) JSONL training data and fine-tunes IndicBERTv2
as a 14-class sequence classifier — replacing the zero-shot NLI approach.

Expected accuracy improvement: ~62% → ~88-92%

Usage:
    # After generate_data.py has run:
    python training/fine_tune.py

    # Custom paths / hyperparams:
    python training/fine_tune.py --train data/synthetic_train.jsonl --epochs 5 --batch 16
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ── Label mapping ─────────────────────────────────────────────────────────
DEPT_IDS = [
    "D01", "D02", "D03", "D04", "D05", "D06", "D07",
    "D08", "D09", "D10", "D11", "D12", "D13", "D14",
]
LABEL2ID = {d: i for i, d in enumerate(DEPT_IDS)}
ID2LABEL = {i: d for i, d in enumerate(DEPT_IDS)}
NUM_LABELS = len(DEPT_IDS)

BASE_MODEL   = "ai4bharat/IndicBERTv2-MLM-Sam-TLM"
OUTPUT_DIR   = Path("training/models/janvedha-classifier")
TRAIN_FILE   = Path("training/data/synthetic_train.jsonl")
VAL_FILE     = Path("training/data/synthetic_train_val.jsonl")


def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_dataset(records: list[dict], tokenizer):
    """Convert raw JSONL records into a HuggingFace Dataset."""
    from datasets import Dataset

    texts  = [r["text"]    for r in records]
    labels = [LABEL2ID.get(r["dept_id"], 0) for r in records]

    encodings = tokenizer(
        texts,
        truncation=True,
        padding="max_length",
        max_length=128,
        return_tensors=None,  # return lists, not tensors (Dataset handles it)
    )
    encodings["labels"] = labels
    return Dataset.from_dict(encodings)


def compute_metrics(eval_pred):
    import numpy as np
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = (preds == labels).mean()
    return {"accuracy": round(float(acc), 4)}


def main(
    train_file: str,
    val_file:   str,
    output_dir: str,
    epochs:     int,
    batch_size: int,
    lr:         float,
) -> None:
    train_path = Path(train_file)
    val_path   = Path(val_file)

    if not train_path.exists():
        sys.exit(f"❌  Training file not found: {train_path}\n"
                 "    Run  python training/generate_data.py  first.")

    logger.info("📂  Loading training data from %s …", train_path)
    train_records = load_jsonl(train_path)
    logger.info("    %d training examples loaded", len(train_records))

    val_records = []
    if val_path.exists():
        val_records = load_jsonl(val_path)
        logger.info("    %d validation examples loaded", len(val_records))
    else:
        logger.warning("⚠️  No validation file found at %s — skipping eval", val_path)

    # ── Load tokeniser ─────────────────────────────────────────────────────
    logger.info("🔠  Loading tokenizer from %s …", BASE_MODEL)
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

    # ── Tokenise datasets ──────────────────────────────────────────────────
    logger.info("🔢  Tokenising …")
    train_dataset = build_dataset(train_records, tokenizer)
    eval_dataset  = build_dataset(val_records, tokenizer) if val_records else None

    # ── Load model (swap NLI head → 14-class head) ─────────────────────────
    logger.info("🤖  Loading base model from %s …", BASE_MODEL)
    from transformers import AutoModelForSequenceClassification
    model = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL,
        num_labels=NUM_LABELS,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
        ignore_mismatched_sizes=True,   # NLI head (3 labels) → classification (14 labels)
    )
    logger.info("    Model loaded. Trainable params: %s M",
                round(sum(p.numel() for p in model.parameters() if p.requires_grad) / 1e6, 1))

    # ── Training arguments ─────────────────────────────────────────────────
    from transformers import TrainingArguments, Trainer

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(out_path / "checkpoints"),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=16 // batch_size if batch_size < 16 else 1,
        learning_rate=lr,
        warmup_steps=50,
        weight_decay=0.01,
        logging_steps=10,
        eval_strategy="epoch" if eval_dataset else "no",
        save_strategy="epoch",
        load_best_model_at_end=True if eval_dataset else False,
        metric_for_best_model="accuracy",
        save_total_limit=2,
        fp16=False,
        dataloader_num_workers=0,  # CRITICAL: 0 workers prevents multiprocessing RAM spikes
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        compute_metrics=compute_metrics,
    )

    # ── Train ──────────────────────────────────────────────────────────────
    logger.info("🚀  Starting fine-tuning …")
    logger.info("    Epochs: %d | Batch: %d | LR: %g", epochs, batch_size, lr)
    
    # Auto-resume logic:
    checkpoint_dir = out_path / "checkpoints"
    resume_from_checkpoint = False
    if checkpoint_dir.exists():
        checkpoints = sorted(checkpoint_dir.glob("checkpoint-*"))
        if checkpoints:
            resume_from_checkpoint = str(checkpoints[-1])
            logger.info("⏳  Found existing checkpoint: %s. Resuming training...", resume_from_checkpoint)

    trainer.train(resume_from_checkpoint=resume_from_checkpoint)

    # ── Evaluate ───────────────────────────────────────────────────────────
    if eval_dataset:
        logger.info("📊  Final evaluation …")
        metrics = trainer.evaluate()
        logger.info("    Val accuracy: %.1f%%", metrics.get("eval_accuracy", 0) * 100)

    # ── Save ───────────────────────────────────────────────────────────────
    logger.info("💾  Saving fine-tuned model to %s …", out_path)
    trainer.save_model(str(out_path))
    tokenizer.save_pretrained(str(out_path))

    # Save label map for classifier_agent.py
    label_map = {"label2id": LABEL2ID, "id2label": {str(k): v for k, v in ID2LABEL.items()}}
    (out_path / "label_map.json").write_text(json.dumps(label_map, indent=2))

    logger.info("\n✅  Fine-tuning complete!")
    logger.info("   Model saved → %s", out_path.resolve())
    logger.info("   Next step: the classifier will auto-load this model on startup.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune IndicBERTv2 on JanVedha civic complaints")
    parser.add_argument("--train",   default=str(TRAIN_FILE), help="Path to train JSONL")
    parser.add_argument("--val",     default=str(VAL_FILE),   help="Path to validation JSONL")
    parser.add_argument("--output",  default=str(OUTPUT_DIR), help="Directory to save fine-tuned model")
    parser.add_argument("--epochs",  type=int,   default=5,   help="Number of training epochs (default: 5)")
    parser.add_argument("--batch",   type=int,   default=4,  help="Per-device batch size (default: 4)")
    parser.add_argument("--lr",      type=float, default=2e-5, help="Learning rate (default: 2e-5)")
    args = parser.parse_args()
    main(args.train, args.val, args.output, args.epochs, args.batch, args.lr)
