# 🧠 CLFIS Machine Learning & Retrieval Pipeline

This directory contains the machine learning, multimodal embedding extraction, and evaluation pipeline for the **Campus Lost-and-Found Intelligence System (CLFIS)**.

## Architecture

1. **Multimodal Embeddings**: Extracts 768-d joint vision-language embeddings using `google/siglip-base-patch16-224`.
2. **OCR Token Mining**: Extracts alphanumeric serial numbers, ID cards, and room keys via Tesseract.
3. **Decay Functions**:
   - Exponential temporal decay ($\lambda = 0.05$).
   - Campus zone spatial proximity and PostGIS Haversine decay.
4. **Evaluation Metrics**: Computes **Recall@K**, **MRR** (Mean Reciprocal Rank), **Precision@K**, and **NDCG@K**.

## Running the Evaluation Benchmark

```bash
python ml/src/evaluation/run_eval.py --dataset ml/data/processed/campus_test_pairs.json --top_k 5
```
