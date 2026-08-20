# ICYQuant — Alpha Cluster Analysis (real data)

- **Generated at**: `2026-08-20T06:25:40.503495+00:00`
- **Candidates**: 22 synthetic-data factors -> **21 independent families**
- **Method**: Spearman rank correlation of factor values on train + validation only (2024-01 .. 2025-12); OOS untouched; average linkage on 1-|corr|, cut at |corr| >= 0.8

## Factor Families

| Family | Size | Representative | Intra |corr| | Best real performer |
|---|---:|---|---:|---|
| F1 | 2 | Alpha038 | 0.82 | Alpha101 (score 0.1348, 0 assets) |
| F2 | 1 | Alpha004 | 0.00 | Alpha004 (score 0.0503, 0 assets) |
| F3 | 1 | Alpha005 | 0.00 | Alpha005 (score 0.1419, 0 assets) |
| F4 | 1 | Alpha008 | 0.00 | Alpha008 (score 0.0886, 0 assets) |
| F5 | 1 | Alpha019 | 0.00 | Alpha019 (score 0.0886, 0 assets) |
| F6 | 1 | Alpha020 | 0.00 | Alpha020 (score 0.1725, 0 assets) |
| F7 | 1 | Alpha021 | 0.00 | Alpha021 (score 0.4935, 3 assets) |
| F8 | 1 | Alpha029 | 0.00 | Alpha029 (score 0.1064, 0 assets) |
| F9 | 1 | Alpha030 | 0.00 | Alpha030 (score 0.1750, 0 assets) |
| F10 | 1 | Alpha032 | 0.00 | Alpha032 (score 0.1325, 0 assets) |
| F11 | 1 | Alpha039 | 0.00 | Alpha039 (score 0.0816, 0 assets) |
| F12 | 1 | Alpha046 | 0.00 | Alpha046 (score 0.1910, 0 assets) |
| F13 | 1 | Alpha047 | 0.00 | Alpha047 (score 0.0702, 0 assets) |
| F14 | 1 | Alpha054 | 0.00 | Alpha054 (score 0.2980, 0 assets) |
| F15 | 1 | Alpha060 | 0.00 | Alpha060 (score 0.1587, 0 assets) |
| F16 | 1 | Alpha063 | 0.00 | Alpha063 (score 0.4635, 0 assets) |
| F17 | 1 | Alpha064 | 0.00 | Alpha064 (score 0.2241, 0 assets) |
| F18 | 1 | Alpha069 | 0.00 | Alpha069 (score 0.0525, 0 assets) |
| F19 | 1 | Alpha089 | 0.00 | Alpha089 (score 0.0448, 0 assets) |
| F20 | 1 | Alpha090 | 0.00 | Alpha090 (score 0.0284, 0 assets) |
| F21 | 1 | Alpha094 | 0.00 | Alpha094 (score 0.3540, 0 assets) |

### F1 — representative `Alpha038` (2 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha101 | 0.8218 | 0.1348 | 0 | -0.028687 | -0.812813 | -0.059122 | REJECTED |
| Alpha038 | 1.0 | 0.1295 | 0 | -0.013467 | 0.299922 | 0.2437 | REJECTED |

### F2 — representative `Alpha004` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha004 | 1.0 | 0.0503 | 0 | -0.012111 | 0.286178 | -0.314033 | REJECTED |

### F3 — representative `Alpha005` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha005 | 1.0 | 0.1419 | 0 | -0.013911 | 0.607833 | 0.1662 | REJECTED |

### F4 — representative `Alpha008` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha008 | 1.0 | 0.0886 | 0 | 0.010533 | 0.633478 | -0.085978 | REJECTED |

### F5 — representative `Alpha019` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha019 | 1.0 | 0.0886 | 0 | -0.000967 | 0.7476 | -0.630922 | REJECTED |

### F6 — representative `Alpha020` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha020 | 1.0 | 0.1725 | 0 | 0.048 | 0.905078 | -0.099644 | REJECTED |

### F7 — representative `Alpha021` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha021 | 1.0 | 0.4935 | 3 | 0.021322 | 0.311125 | 0.571456 | CANDIDATE |

### F8 — representative `Alpha029` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha029 | 1.0 | 0.1064 | 0 | 0.035667 | 0.486189 | -0.037089 | REJECTED |

### F9 — representative `Alpha030` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha030 | 1.0 | 0.175 | 0 | 0.034862 | 1.083363 | -0.259911 | REJECTED |

### F10 — representative `Alpha032` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha032 | 1.0 | 0.1325 | 0 | 0.031467 | 0.759511 | -0.030422 | REJECTED |

### F11 — representative `Alpha039` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha039 | 1.0 | 0.0816 | 0 | -0.02015 | 0.458275 | -0.519678 | REJECTED |

### F12 — representative `Alpha046` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha046 | 1.0 | 0.191 | 0 | -0.009933 | 0.1782 | 0.503422 | REJECTED |

### F13 — representative `Alpha047` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha047 | 1.0 | 0.0702 | 0 | -0.006763 | 0.5209 | -0.452011 | REJECTED |

### F14 — representative `Alpha054` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha054 | 1.0 | 0.298 | 0 | 0.010313 | 0.529937 | 0.714156 | REJECTED |

### F15 — representative `Alpha060` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha060 | 1.0 | 0.1587 | 0 | -0.00155 | 0.4349 | 0.340556 | REJECTED |

### F16 — representative `Alpha063` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha063 | 1.0 | 0.4635 | 0 | 0.054688 | 1.176262 | 0.804922 | REJECTED |

### F17 — representative `Alpha064` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha064 | 1.0 | 0.2241 | 0 | 0.02735 | 0.441775 | 0.432967 | REJECTED |

### F18 — representative `Alpha069` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha069 | 1.0 | 0.0525 | 0 | -0.0004 | 0.444925 | -0.136 | REJECTED |

### F19 — representative `Alpha089` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha089 | 1.0 | 0.0448 | 0 | -0.010863 | 0.101237 | 0.057522 | REJECTED |

### F20 — representative `Alpha090` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha090 | 1.0 | 0.0284 | 0 | -0.01235 | 0.0961 | -0.436844 | REJECTED |

### F21 — representative `Alpha094` (1 members)

| Alpha | \|corr\| to rep | Real score | Real assets | Mean OOS IC | Mean OOS ICIR | Mean OOS Sharpe | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| Alpha094 | 1.0 | 0.354 | 0 | 0.010313 | 2.385414 | 0.197567 | REJECTED |

## Threshold Sensitivity

| \|corr\| threshold | Families | Multi-member families |
|---:|---:|---|
| 0.50 | 9 | {Alpha004,Alpha005,Alpha008,Alpha019,Alpha029,Alpha032,Alpha039,Alpha047,Alpha063}; {Alpha038,Alpha054,Alpha060,Alpha101}; {Alpha030,Alpha090}; {Alpha069,Alpha094} |
| 0.60 | 15 | {Alpha004,Alpha005,Alpha032,Alpha047}; {Alpha038,Alpha054,Alpha060,Alpha101}; {Alpha019,Alpha039} |
| 0.65 | 15 | {Alpha004,Alpha005,Alpha032,Alpha047}; {Alpha038,Alpha054,Alpha060,Alpha101}; {Alpha019,Alpha039} |
| 0.70 | 16 | {Alpha038,Alpha054,Alpha060,Alpha101}; {Alpha005,Alpha032,Alpha047}; {Alpha019,Alpha039} |
| 0.75 | 19 | {Alpha019,Alpha039}; {Alpha038,Alpha101}; {Alpha054,Alpha060} |
| 0.80 | 21 | {Alpha038,Alpha101} |

## Recommended De-correlated Pool (one per family at |corr| >= 0.65)

| Family | Picked (best real score) | Dropped (redundant) | Intra |corr| | Real score | Real assets | Mean OOS ICIR | Mean OOS Sharpe |
|---|---|---|---:|---:|---:|---:|---:|
| P1 | Alpha005 | Alpha004, Alpha032, Alpha047 | 0.74 | 0.1419 | 0 | 0.607833 | 0.1662 |
| P2 | Alpha054 | Alpha038, Alpha060, Alpha101 | 0.79 | 0.298 | 0 | 0.529937 | 0.714156 |
| P3 | Alpha019 | Alpha039 | 0.78 | 0.0886 | 0 | 0.7476 | -0.630922 |
| P4 | Alpha008 | — | 0.00 | 0.0886 | 0 | 0.633478 | -0.085978 |
| P5 | Alpha020 | — | 0.00 | 0.1725 | 0 | 0.905078 | -0.099644 |
| P6 | Alpha021 | — | 0.00 | 0.4935 | 3 | 0.311125 | 0.571456 |
| P7 | Alpha029 | — | 0.00 | 0.1064 | 0 | 0.486189 | -0.037089 |
| P8 | Alpha030 | — | 0.00 | 0.175 | 0 | 1.083363 | -0.259911 |
| P9 | Alpha046 | — | 0.00 | 0.191 | 0 | 0.1782 | 0.503422 |
| P10 | Alpha063 | — | 0.00 | 0.4635 | 0 | 1.176262 | 0.804922 |
| P11 | Alpha064 | — | 0.00 | 0.2241 | 0 | 0.441775 | 0.432967 |
| P12 | Alpha069 | — | 0.00 | 0.0525 | 0 | 0.444925 | -0.136 |
| P13 | Alpha089 | — | 0.00 | 0.0448 | 0 | 0.101237 | 0.057522 |
| P14 | Alpha090 | — | 0.00 | 0.0284 | 0 | 0.0961 | -0.436844 |
| P15 | Alpha094 | — | 0.00 | 0.354 | 0 | 2.385414 | 0.197567 |

## Cross-Family |corr| (representatives)

|  | Alpha038 | Alpha004 | Alpha005 | Alpha008 | Alpha019 | Alpha020 | Alpha021 | Alpha029 | Alpha030 | Alpha032 | Alpha039 | Alpha046 | Alpha047 | Alpha054 | Alpha060 | Alpha063 | Alpha064 | Alpha069 | Alpha089 | Alpha090 | Alpha094 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Alpha038 | 1.00 | 0.67 | 0.82 | 0.50 | 0.48 | 0.25 | 0.48 | 0.35 | 0.62 | 0.68 | 0.60 | 0.36 | 0.63 | 0.68 | 0.78 | 0.44 | 0.35 | 0.28 | 0.31 | 0.68 | 0.48 |
| Alpha004 | 0.67 | 1.00 | 0.67 | 0.60 | 0.44 | 0.49 | 0.55 | 0.47 | 0.60 | 0.67 | 0.61 | 0.37 | 0.74 | 0.19 | 0.40 | 0.54 | 0.45 | 0.35 | 0.43 | 0.61 | 0.54 |
| Alpha005 | 0.82 | 0.67 | 1.00 | 0.58 | 0.53 | 0.31 | 0.53 | 0.46 | 0.57 | 0.69 | 0.70 | 0.43 | 0.74 | 0.61 | 0.73 | 0.53 | 0.36 | 0.38 | 0.38 | 0.63 | 0.54 |
| Alpha008 | 0.50 | 0.60 | 0.58 | 1.00 | 0.44 | 0.26 | 0.43 | 0.48 | 0.41 | 0.50 | 0.55 | 0.53 | 0.69 | 0.19 | 0.35 | 0.56 | 0.44 | 0.38 | 0.53 | 0.42 | 0.44 |
| Alpha019 | 0.48 | 0.44 | 0.53 | 0.44 | 1.00 | 0.21 | 0.44 | 0.47 | 0.28 | 0.41 | 0.78 | 0.34 | 0.60 | 0.14 | 0.35 | 0.42 | 0.27 | 0.37 | 0.30 | 0.36 | 0.35 |
| Alpha020 | 0.25 | 0.49 | 0.31 | 0.26 | 0.21 | 1.00 | 0.27 | 0.14 | 0.35 | 0.35 | 0.25 | 0.18 | 0.32 | 0.00 | 0.09 | 0.20 | 0.21 | 0.06 | 0.14 | 0.35 | 0.26 |
| Alpha021 | 0.48 | 0.55 | 0.53 | 0.43 | 0.44 | 0.27 | 1.00 | 0.37 | 0.42 | 0.48 | 0.50 | 0.32 | 0.56 | 0.16 | 0.28 | 0.37 | 0.32 | 0.31 | 0.34 | 0.42 | 0.40 |
| Alpha029 | 0.35 | 0.47 | 0.46 | 0.48 | 0.47 | 0.14 | 0.37 | 1.00 | 0.27 | 0.45 | 0.54 | 0.29 | 0.54 | 0.04 | 0.27 | 0.54 | 0.39 | 0.32 | 0.34 | 0.32 | 0.35 |
| Alpha030 | 0.62 | 0.60 | 0.57 | 0.41 | 0.28 | 0.35 | 0.42 | 0.27 | 1.00 | 0.50 | 0.41 | 0.23 | 0.52 | 0.34 | 0.42 | 0.41 | 0.32 | 0.18 | 0.28 | 0.57 | 0.34 |
| Alpha032 | 0.68 | 0.67 | 0.69 | 0.50 | 0.41 | 0.35 | 0.48 | 0.45 | 0.50 | 1.00 | 0.56 | 0.31 | 0.73 | 0.29 | 0.51 | 0.45 | 0.36 | 0.34 | 0.29 | 0.57 | 0.50 |
| Alpha039 | 0.60 | 0.61 | 0.70 | 0.55 | 0.78 | 0.25 | 0.50 | 0.54 | 0.41 | 0.56 | 1.00 | 0.43 | 0.76 | 0.20 | 0.41 | 0.52 | 0.32 | 0.49 | 0.46 | 0.46 | 0.53 |
| Alpha046 | 0.36 | 0.37 | 0.43 | 0.53 | 0.34 | 0.18 | 0.32 | 0.29 | 0.23 | 0.31 | 0.43 | 1.00 | 0.41 | 0.13 | 0.29 | 0.32 | 0.22 | 0.27 | 0.40 | 0.25 | 0.46 |
| Alpha047 | 0.63 | 0.74 | 0.74 | 0.69 | 0.60 | 0.32 | 0.56 | 0.54 | 0.52 | 0.73 | 0.76 | 0.41 | 1.00 | 0.18 | 0.38 | 0.63 | 0.46 | 0.51 | 0.46 | 0.55 | 0.61 |
| Alpha054 | 0.68 | 0.19 | 0.61 | 0.19 | 0.14 | 0.00 | 0.16 | 0.04 | 0.34 | 0.29 | 0.20 | 0.13 | 0.18 | 1.00 | 0.78 | 0.12 | 0.09 | 0.07 | 0.05 | 0.40 | 0.15 |
| Alpha060 | 0.78 | 0.40 | 0.73 | 0.35 | 0.35 | 0.09 | 0.28 | 0.27 | 0.42 | 0.51 | 0.41 | 0.29 | 0.38 | 0.78 | 1.00 | 0.28 | 0.18 | 0.17 | 0.17 | 0.50 | 0.30 |
| Alpha063 | 0.44 | 0.54 | 0.53 | 0.56 | 0.42 | 0.20 | 0.37 | 0.54 | 0.41 | 0.45 | 0.52 | 0.32 | 0.63 | 0.12 | 0.28 | 1.00 | 0.53 | 0.39 | 0.38 | 0.39 | 0.48 |
| Alpha064 | 0.35 | 0.45 | 0.36 | 0.44 | 0.27 | 0.21 | 0.32 | 0.39 | 0.32 | 0.36 | 0.32 | 0.22 | 0.46 | 0.09 | 0.18 | 0.53 | 1.00 | 0.22 | 0.25 | 0.33 | 0.28 |
| Alpha069 | 0.28 | 0.35 | 0.38 | 0.38 | 0.37 | 0.06 | 0.31 | 0.32 | 0.18 | 0.34 | 0.49 | 0.27 | 0.51 | 0.07 | 0.17 | 0.39 | 0.22 | 1.00 | 0.36 | 0.26 | 0.53 |
| Alpha089 | 0.31 | 0.43 | 0.38 | 0.53 | 0.30 | 0.14 | 0.34 | 0.34 | 0.28 | 0.29 | 0.46 | 0.40 | 0.46 | 0.05 | 0.17 | 0.38 | 0.25 | 0.36 | 1.00 | 0.25 | 0.41 |
| Alpha090 | 0.68 | 0.61 | 0.63 | 0.42 | 0.36 | 0.35 | 0.42 | 0.32 | 0.57 | 0.57 | 0.46 | 0.25 | 0.55 | 0.40 | 0.50 | 0.39 | 0.33 | 0.26 | 0.25 | 1.00 | 0.36 |
| Alpha094 | 0.48 | 0.54 | 0.54 | 0.44 | 0.35 | 0.26 | 0.40 | 0.35 | 0.34 | 0.50 | 0.53 | 0.46 | 0.61 | 0.15 | 0.30 | 0.48 | 0.28 | 0.53 | 0.41 | 0.36 | 1.00 |

## Watch-list affinity (real-side strong alphas vs families)

| Alpha | Real score | Best family | Mean |corr| to family |
|---|---:|---|---:|
| Alpha035 | 0.5125 | F1 | 0.767 |
| Alpha026 | 0.4935 | F11 | 0.2355 |
| Alpha072 | 0.4276 | F8 | 0.1479 |
| Alpha040 | 0.3902 | F8 | 0.1857 |
| Alpha045 | 0.353 | F2 | 0.1413 |

---
_Clustering is structural (factor values, train+validation bars only); OOS data was never used. Representatives are medoids; families cut at |corr| >= 0.80 (average linkage)._