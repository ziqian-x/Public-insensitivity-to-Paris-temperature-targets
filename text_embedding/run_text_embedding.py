#!/usr/bin/env python3
"""Reproduce Figure 2 and Table S12 for the manuscript.

Default mode uses cached embedding test results so replication works quickly.
Use --recompute to run all embedding models from scratch.
"""

from __future__ import annotations

import argparse
import math
import pickle
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SEED = 123
TEXT_COL = "Q23"
COND_COL = "temp_c"
CONSENT_COL = "QID2"
ATTN_COL = "QID6"
DURATION_COL = "Duration (in seconds)"
FINISHED_COL = "Finished"

MODELS = [
    (
        "sentence-transformers/all-mpnet-base-v2",
        "MPNet-Base",
        False,
        "e8c3b32edf5434bc2275fc9bab85f82640a19130",
    ),
    (
        "sentence-transformers/all-MiniLM-L6-v2",
        "MiniLM-L6",
        False,
        "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
    ),
    (
        "intfloat/e5-large-v2",
        "E5-Large",
        True,
        "f169b11e22de13617baa190a028a32f3493550b6",
    ),
    (
        "BAAI/bge-large-en-v1.5",
        "BGE-Large",
        False,
        "d4aa6901d3a41ba39fb536a557fa166f842b0e09",
    ),
    (
        "mixedbread-ai/mxbai-embed-large-v1",
        "Mxbai-Large",
        False,
        "b33106f585b9ce46904ad7443a3b52b7a63e231c",
    ),
]
EXPECTED_MODEL_VERSION_ROWS = len(MODELS) * 2


def clean_text_remove_temperature_cues(text: str) -> str:
    text = str(text)
    text = re.sub(r"\b\d+(\.\d+)?\b", "", text)
    text = re.sub(r"[°℃℉]", "", text)
    text = re.sub(r"\b(degree|degrees|celsius|fahrenheit)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b[CF]\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess_text_data(data_path: Path) -> pd.DataFrame:
    df = pd.read_csv(data_path, dtype=str)
    required = [TEXT_COL, COND_COL, CONSENT_COL, ATTN_COL, DURATION_COL, FINISHED_COL]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {data_path}: {missing}")

    # These guards allow the workflow to read either the sanitized public file
    # or an original Qualtrics export with two metadata rows.
    if "StartDate" in df.columns:
        start = df["StartDate"].fillna("")
        df = df[(start != "Start Date") & ~start.str.startswith('{"ImportId"')].copy()

    finished = df[FINISHED_COL].fillna("").str.upper().eq("TRUE")
    df = df[
        finished
        & df[CONSENT_COL].eq("I agree")
        & df[ATTN_COL].eq("Somewhat disagree")
    ].copy()
    df[DURATION_COL] = pd.to_numeric(df[DURATION_COL], errors="coerce")
    duration_median = float(df[DURATION_COL].median())
    speed_threshold = duration_median / 3.0
    df = df[df[DURATION_COL].ge(speed_threshold)].copy()
    df = df.dropna(subset=[TEXT_COL, COND_COL]).copy()
    df["text_raw"] = df[TEXT_COL].astype(str)
    df["text_clean"] = df["text_raw"].apply(clean_text_remove_temperature_cues)
    df["temp_condition"] = df[COND_COL].astype(str)
    result = df.reset_index(drop=True)
    result.attrs["duration_median"] = duration_median
    result.attrs["speed_threshold"] = speed_threshold
    return result


def compute_similarity_stats(embeddings: np.ndarray, labels: np.ndarray):
    from sklearn.metrics.pairwise import cosine_similarity

    if not np.isfinite(embeddings).all():
        raise ValueError("Embedding matrix contains non-finite values.")
    sim_matrix = cosine_similarity(embeddings, embeddings)
    if not np.isfinite(sim_matrix).all():
        raise ValueError("Cosine-similarity matrix contains non-finite values.")
    iu = np.triu_indices(len(labels), k=1)
    pair_sims = sim_matrix[iu]
    within_mask = labels[iu[0]] == labels[iu[1]]

    within_vals = pair_sims[within_mask]
    between_vals = pair_sims[~within_mask]
    within_mean = float(within_vals.mean()) if within_vals.size else 0.0
    between_mean = float(between_vals.mean()) if between_vals.size else 0.0
    delta = within_mean - between_mean
    return within_mean, between_mean, delta, pair_sims, iu


def run_permutation_test(pair_sims, labels, iu, observed_delta, n_perm=1000, seed=SEED):
    rng = np.random.default_rng(seed)
    null_dist = np.empty(n_perm)
    for i in range(n_perm):
        perm = rng.permutation(labels)
        within_mask = perm[iu[0]] == perm[iu[1]]
        null_dist[i] = pair_sims[within_mask].mean() - pair_sims[~within_mask].mean()

    p_value = (np.sum(np.abs(null_dist) >= abs(observed_delta)) + 1) / (n_perm + 1)
    return float(p_value), null_dist


def recompute_embeddings(df: pd.DataFrame, n_perm: int) -> list[dict]:
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "sentence-transformers is required for --recompute. "
            "Install requirements or run without --recompute to use cached results."
        ) from exc

    labels = df["temp_condition"].to_numpy()
    texts_raw = df["text_raw"].tolist()
    texts_clean = df["text_clean"].tolist()

    results = []
    for model_id, short_name, use_prefix, revision in MODELS:
        model = SentenceTransformer(model_id, revision=revision)
        for version, text_data in (("RAW", texts_raw), ("CLEAN", texts_clean)):
            if use_prefix and "e5" in model_id:
                text_data = [f"passage: {t}" for t in text_data]

            embeddings = model.encode(
                text_data,
                batch_size=64,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            within_mean, between_mean, delta_obs, pair_sims, iu = compute_similarity_stats(embeddings, labels)
            p_value, null_dist = run_permutation_test(
                pair_sims,
                labels,
                iu,
                observed_delta=delta_obs,
                n_perm=n_perm,
                seed=SEED,
            )
            null_sd = float(np.std(null_dist, ddof=1))
            results.append(
                {
                    "Model": short_name,
                    "Model_ID": model_id,
                    "Version": version,
                    "N": int(len(labels)),
                    "Within_Mean": float(within_mean),
                    "Between_Mean": float(between_mean),
                    "Delta_Obs": float(delta_obs),
                    "P_Value": float(p_value),
                    "Null_Mean": float(np.mean(null_dist)),
                    "Null_SD": null_sd,
                    "Z_Score": float(delta_obs / null_sd) if null_sd > 0 else math.nan,
                }
            )
    return results


def load_results(cache_path: Path, recompute: bool, df: pd.DataFrame, n_perm: int) -> pd.DataFrame:
    if recompute:
        results = recompute_embeddings(df, n_perm=n_perm)
        with cache_path.open("wb") as f:
            pickle.dump(results, f)
    else:
        if not cache_path.exists():
            raise FileNotFoundError(
                f"Cache not found: {cache_path}. Run with --recompute to generate it."
            )
        with cache_path.open("rb") as f:
            results = pickle.load(f)

    result_frame = pd.DataFrame(results)
    cached_ns = set(pd.to_numeric(result_frame["N"], errors="coerce").dropna().astype(int))
    if cached_ns != {len(df)}:
        raise ValueError(
            f"Cached embedding results use N={sorted(cached_ns)}, but the current "
            f"analytic text sample has N={len(df)}. Run with --recompute."
        )
    return result_frame


def make_table_s12(df_results: pd.DataFrame) -> pd.DataFrame:
    if len(df_results) != EXPECTED_MODEL_VERSION_ROWS:
        raise ValueError(
            f"Expected {EXPECTED_MODEL_VERSION_ROWS} model-version rows, got {len(df_results)}."
        )

    table = df_results.copy()
    table["Significance"] = np.where(
        table["P_Value"] < 0.05,
        "Sig.",
        np.where(table["P_Value"] < 0.10, "Marginal", "Non-sig."),
    )
    return table[
        [
            "Model",
            "Version",
            "Delta_Obs",
            "P_Value",
            "Within_Mean",
            "Between_Mean",
            "Significance",
        ]
    ].sort_values(["Model", "Version"])


def make_figure2(df_results: pd.DataFrame, figure_path: Path):
    raw = df_results[df_results["Version"] == "RAW"].copy()
    model_order = [short_name for _, short_name, _, _ in MODELS]
    raw["Model"] = pd.Categorical(raw["Model"], categories=model_order, ordered=True)
    raw = raw.sort_values("Model")

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["xtick.major.width"] = 0.8
    plt.rcParams["ytick.major.width"] = 0.8

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=300)
    x = np.arange(len(raw))
    width = 0.35
    within = raw["Within_Mean"].to_numpy()
    between = raw["Between_Mean"].to_numpy()
    ax.bar(x - width / 2, within, width=width, color="#111111", label="Within condition")
    ax.bar(x + width / 2, between, width=width, color="#A8A8A8", label="Between conditions")
    ax.set_xticks(x)
    ax.set_xticklabels(raw["Model"].tolist(), rotation=0)
    ax.set_ylabel("Mean cosine similarity")
    ax.set_xlabel("Sentence embedding model")
    ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.5, 1.16))
    ax.set_ylim(0, max(within.max(), between.max()) + 0.08)
    for i, (_, row) in enumerate(raw.iterrows()):
        ax.text(
            i,
            max(row["Within_Mean"], row["Between_Mean"]) + 0.01,
            f"Δ={row['Delta_Obs']:.4f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.spines[["top", "right"]].set_visible(False)

    figure_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(figure_path, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reproduce Figure 2 and Table S12.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("../data/validation1/validation1.csv"),
        help="Path to validation1.csv",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path("results_cache.pkl"),
        help="Cache path for embedding results",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("../outputs/tables"),
        help="Output folder for replication tables",
    )
    parser.add_argument(
        "--figure",
        type=Path,
        default=Path("../outputs/figures/Figure2.png"),
        help="Output figure path",
    )
    parser.add_argument(
        "--n-perm",
        type=int,
        default=1000,
        help="Permutation iterations when --recompute is set",
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="Recompute embeddings instead of using cached results",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent

    data_path = (script_dir / args.data).resolve()
    cache_path = (script_dir / args.cache).resolve()
    outdir = (script_dir / args.outdir).resolve()
    figure_path = (script_dir / args.figure).resolve()

    df_text = preprocess_text_data(data_path)
    df_results = load_results(cache_path=cache_path, recompute=args.recompute, df=df_text, n_perm=args.n_perm)

    outdir.mkdir(parents=True, exist_ok=True)
    full_results_path = outdir / "embedding_results_full.csv"
    table_s12_path = outdir / "table_s12.csv"
    df_results.to_csv(full_results_path, index=False)

    table_s12 = make_table_s12(df_results)
    table_s12.to_csv(table_s12_path, index=False)

    make_figure2(df_results=df_results, figure_path=figure_path)

    print(f"Analytic N for text analysis: {len(df_text)}")
    print(f"Median duration after consent and attention checks: {df_text.attrs['duration_median']:.1f} s")
    print(f"Speed threshold: {df_text.attrs['speed_threshold']:.3f} s")
    print(f"Saved: {full_results_path}")
    print(f"Saved: {table_s12_path}")
    print(f"Saved: {figure_path}")


if __name__ == "__main__":
    main()
