# LikBy Profile & Discovery Feature Specification

---

## 1. Profile Attributes

| Field | Format / Validation | Visibility |
|:---|:---|:---:|
| `likby_id` | Alphanumeric `[a-z0-9_]{3,24}` | Public |
| `display_name` | String (1-32 chars, sanitized) | Public |
| `age` | Integer (18 - 99 required) | Public |
| `gender` | `male`, `female`, `non_binary`, `other` | Public |
| `target_gender` | `any`, `male`, `female`, `same` | Private filter |
| `languages` | ISO language codes (e.g., `["en", "hi"]`) | Public |
| `bio` | Max 250 characters | Public |
| `photo` | Telegram `file_id` (content-protected) | Public |

---

## 2. Discovery Compatibility Algorithm

The compatibility scorer (`src/likby/services/scorer.py`) calculates a deterministic score from 0.0 to 1.0:
- **Gender Compatibility (0.35 weight):** Reciprocal gender preference matching.
- **Age Compatibility (0.35 weight):** Bell curve decay based on delta from preferred age range.
- **Language Overlap (0.30 weight):** Jaccard similarity across shared spoken languages.
- **Incompatible filters yield an absolute score of 0.0.**
